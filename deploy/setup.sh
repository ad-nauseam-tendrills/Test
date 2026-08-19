#!/usr/bin/env bash
#
# One-time production setup for a single VM.
#
#   ./deploy/setup.sh
#
# Detects the droplet's public IP, derives a free HTTPS-capable hostname
# from it via sslip.io, and writes the config files. Prints the exact
# redirect URI to register with Meta.
#
# Safe to re-run: it never overwrites an existing backend/.env.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Detecting public IP..."
PUBLIC_IP="${PUBLIC_IP:-$(curl -fsS --max-time 10 https://api.ipify.org)}"
if [[ -z "$PUBLIC_IP" ]]; then
	echo "Could not detect the public IP. Re-run with: PUBLIC_IP=1.2.3.4 ./deploy/setup.sh" >&2
	exit 1
fi
echo "    public IP: $PUBLIC_IP"

# sslip.io resolves <dashed-ip>.sslip.io to that IP, and Let's Encrypt
# will issue a certificate for it -- so a valid HTTPS hostname needs no
# domain purchase. Override with SITE_ADDRESS=your.domain.com if you own
# a domain and have pointed an A record at this machine.
DEFAULT_HOST="${PUBLIC_IP//./-}.sslip.io"
SITE_ADDRESS="${SITE_ADDRESS:-$DEFAULT_HOST}"
PUBLIC_URL="https://${SITE_ADDRESS}"
REDIRECT_URI="${PUBLIC_URL}/api/v1/accounts/meta/callback"

echo "==> Hostname: $SITE_ADDRESS"

# --- Root .env: consumed by docker compose variable substitution --------
# Preserve an existing database password: regenerating it would leave the
# already-initialized Postgres volume unreachable.
if [[ -f .env ]] && grep -q '^POSTGRES_PASSWORD=' .env; then
	POSTGRES_PASSWORD="$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
	echo "==> Reusing existing POSTGRES_PASSWORD"
else
	POSTGRES_PASSWORD="$(openssl rand -hex 24)"
	echo "==> Generated a random POSTGRES_PASSWORD"
fi

cat > .env <<EOF
SITE_ADDRESS=${SITE_ADDRESS}
PUBLIC_URL=${PUBLIC_URL}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF
chmod 600 .env
echo "==> Wrote .env"

# --- backend/.env: all application configuration ------------------------
if [[ -f backend/.env ]]; then
	echo "==> backend/.env already exists, leaving it untouched."
else
	cp backend/.env.example backend/.env
	SECRET_KEY="$(openssl rand -hex 32)"
	# Point the app at its public URL. Meta credentials stay blank for
	# the operator to paste in.
	sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" backend/.env
	sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=${PUBLIC_URL}|" backend/.env
	sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=[\"${PUBLIC_URL}\"]|" backend/.env
	sed -i "s|^META_REDIRECT_URI=.*|META_REDIRECT_URI=${REDIRECT_URI}|" backend/.env
	chmod 600 backend/.env
	echo "==> Wrote backend/.env (generated a random SECRET_KEY)"
fi

cat <<EOF

------------------------------------------------------------------
Next steps
------------------------------------------------------------------

1. Register this EXACT redirect URI in your Meta app, under
   Instagram -> API setup with Instagram business login ->
   Business login settings:

     ${REDIRECT_URI}

2. Put your Instagram App ID and Secret into backend/.env:

     nano backend/.env
     # set META_APP_ID and META_APP_SECRET

3. Start everything:

     docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

4. Open ${PUBLIC_URL}

   The first request may take ~30s while Caddy obtains a TLS
   certificate. Ports 80 and 443 must be open for that to succeed.

------------------------------------------------------------------
EOF
