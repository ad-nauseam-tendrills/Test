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

# --- Memory check -------------------------------------------------------
# The Next.js production build and the OpenCV/numpy wheels need well over
# 512 MB. On a small droplet Docker gets OOM-killed mid-build with an
# error that does not mention memory ("exit code 137", or a truncated
# npm/pip failure), so this checks up front and offers swap instead.
TOTAL_RAM_MB=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)
SWAP_MB=$(awk '/SwapTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)
USABLE_MB=$((TOTAL_RAM_MB + SWAP_MB))
RECOMMENDED_MB=2048

if (( TOTAL_RAM_MB > 0 && USABLE_MB < RECOMMENDED_MB )); then
	echo "==> WARNING: ${TOTAL_RAM_MB} MB RAM + ${SWAP_MB} MB swap detected."
	echo "    The build needs roughly ${RECOMMENDED_MB} MB. Without more, Docker"
	echo "    will be OOM-killed partway through (often 'exit code 137')."
	NEEDED_SWAP_MB=$(( RECOMMENDED_MB - USABLE_MB ))
	# Round up to the next whole GB, with 2 GB as a sensible floor.
	SWAP_GB=$(( (NEEDED_SWAP_MB + 1023) / 1024 ))
	(( SWAP_GB < 2 )) && SWAP_GB=2

	if [[ "${AUTO_SWAP:-}" == "1" ]] || { [[ -t 0 ]] && read -rp "    Create a ${SWAP_GB}GB swapfile now? [y/N] " reply && [[ "$reply" =~ ^[Yy]$ ]]; }; then
		if [[ -f /swapfile ]]; then
			echo "    /swapfile already exists, leaving it alone."
		else
			echo "==> Creating ${SWAP_GB}GB swapfile (needs root)..."
			sudo fallocate -l "${SWAP_GB}G" /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=$((SWAP_GB * 1024))
			sudo chmod 600 /swapfile
			sudo mkswap /swapfile
			sudo swapon /swapfile
			# Persist across reboots.
			grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
			echo "    Swap active: $(free -h | awk '/Swap/ {print $2}')"
		fi
	else
		echo "    Continuing without swap. If the build dies, re-run with AUTO_SWAP=1."
	fi
	echo
fi

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
