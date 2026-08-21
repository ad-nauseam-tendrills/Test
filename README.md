# Aperture — Instagram Post Optimization (MVP v0.1)

Aperture helps visual artists and photographers prepare and post images with
more intention: connect an Instagram professional account, import historical
post performance, upload a new image, and get a measurable technical read
plus rule-based recommendations grounded in the account's own history.

**Aperture never promises a specific number of likes or followers, and it
never manipulates engagement.** Every score in the product is an explicit
heuristic derived from measurable image properties and the account's own
historical data — never a prediction. See [Scoring philosophy](#scoring-philosophy) below.

## Stack

| Layer | Tech |
| --- | --- |
| Frontend | Next.js (App Router) · TypeScript · React · Tailwind CSS |
| Backend | Python · FastAPI · SQLAlchemy · Pydantic · Alembic |
| Database | PostgreSQL |
| Image processing | Pillow · OpenCV | 
| Infra | Docker Compose |

## Project structure

```
backend/
  app/
    api/routes/         # auth, accounts, posts, analytics, images, settings
    core/                # config, security, storage helpers
    db/                  # SQLAlchemy session + declarative base
    models/              # ORM models (see Data model below)
    schemas/             # Pydantic request/response models
    services/
      instagram/         # InstagramProvider abstraction (Meta + dev-only mock)
      analytics/         # engagement, normalization, timing, audience, captions
      image_analysis/    # Pillow/OpenCV measurable-property extraction
      image_processing/  # Artwork Integrity optimization engine
      recommendations/   # rule-based recommendations + heuristic scoring
      captions/          # caption suggestions (Anthropic or OpenAI)
    tests/                # pytest suite (182 tests)
  alembic/                # migrations
  scripts/                # seed_mock_data.py, purge_mock_data.py (dev only)
frontend/
  app/                    # /login /dashboard /history /upload /post/[id] /settings
  components/
    ui/                   # Button, Card, ScoreRing, BarChart, ...
    layout/                # Nav, RequireAuth
    dashboard/, upload/, post/
  lib/                    # api client, auth context, formatting helpers
  types/                  # TypeScript types mirroring backend schemas
docker-compose.yml
```

## Quick start (Docker Compose)

```bash
cp backend/.env.example backend/.env   # required -- compose reads this
cp frontend/.env.example frontend/.env.local   # optional, only for `npm run dev` outside Docker

docker compose up --build
```

All backend configuration, including Meta credentials, lives in
**`backend/.env`** — that is the only file you need to edit. Compose
overrides just the container-specific values (database host, storage
paths), so the same file works for Docker and for local development.

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (docs at http://localhost:8000/docs)
- Postgres: localhost:5432 (user/pass `postgres` / `postgres`, db `instaopt`)

The backend container runs `alembic upgrade head` automatically on startup.

Then open the app and use **Connect Instagram** (on the dashboard, or on
the settings page) to connect a real account — see
[Connecting a real Instagram account](#connecting-a-real-instagram-account)
for the Meta app setup that requires.

### Demo data (development only)

There is a mock provider that fabricates 60 realistic historical posts
locally, for working on the analytics and UI without a Meta app. It is
**off by default**, because on a real deployment it fills the dashboard
with posts the owner never made and skews every recommendation derived
from them:

```bash
# Enable it in backend/.env: ENABLE_MOCK_PROVIDER=true
docker compose exec backend env ENABLE_MOCK_PROVIDER=true \
  python -m scripts.seed_mock_data
```

To undo it — including on a deployment that was seeded before a real
account was connected:

```bash
docker compose exec backend python -m scripts.purge_mock_data
docker compose exec backend python -m scripts.purge_mock_data --user  # also drop the demo user
```

Individual accounts can also be removed from the settings page with
**Remove**, which deletes the account and every post imported from it.

## Deploying to a single VM

A VM is the easier target for a real Instagram connection than local
development, because its address is stable — the OAuth redirect URI is
registered once and never changes.

```bash
git clone -b claude/instagram-optimization-mvp-j7z4ja \
  https://github.com/ad-nauseam-tendrills/Test.git
cd Test
./deploy/setup.sh
```

`setup.sh` detects the machine's public IP, derives an HTTPS-capable
hostname from it, generates a random `SECRET_KEY` and database password,
writes both env files with mode `600`, and prints the exact redirect URI
to register with Meta. It never overwrites an existing `backend/.env`, so
it is safe to re-run.

Then add `META_APP_ID` / `META_APP_SECRET` to `backend/.env` and:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

**If the machine already runs a web server** (nginx, Apache, Traefik),
do not use `docker-compose.prod.yml` — its Caddy would fight for ports
80/443 and take the existing site down. Use the behind-a-proxy overlay
instead, which binds every service to `127.0.0.1` and starts no proxy of
its own:

```bash
docker compose -f docker-compose.yml \
  -f docker-compose.behind-proxy.yml up -d --build
```

Then add `deploy/nginx-site.conf.example` as a vhost for your hostname
and issue a certificate with `certbot --nginx -d your.hostname`. The
vhost claims one `server_name`, so other sites are unaffected. Note it
raises `client_max_body_size` to 30M — nginx's 1M default would reject
image uploads with a 413 before they ever reach the app. `setup.sh`
detects an existing listener on port 80 and prints these steps for you.

**Memory.** The Next.js build and the OpenCV/numpy wheels need roughly
2 GB. On a smaller droplet Docker is OOM-killed mid-build with an error
that never mentions memory (typically `exit code 137`). `setup.sh` checks
this up front and offers to create a swapfile; pass `AUTO_SWAP=1` to skip
the prompt.

**No domain required.** The default hostname uses
[sslip.io](https://sslip.io), which resolves `1-2-3-4.sslip.io` to
`1.2.3.4` and works with Let's Encrypt, so Caddy provisions a real
certificate without a domain purchase. If you own a domain, point an A
record at the machine and run `SITE_ADDRESS=your.domain.com ./deploy/setup.sh`.

**Networking.** Caddy terminates TLS and serves the API and frontend from
one origin (`/api/*` to the backend, everything else to the frontend), so
there is no CORS configuration and only one hostname to register. Every
other service binds to `127.0.0.1` only — reachable over SSH for
debugging, not from the internet. Note that Docker writes iptables rules
that bypass `ufw`, so a publicly-bound port stays reachable even with the
firewall enabled; the production overlay uses `!override` on each `ports`
list because compose otherwise *merges* them and would silently retain
the base file's public bindings.

## Local development (without Docker)

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL to point at your local Postgres
alembic upgrade head
ENABLE_MOCK_PROVIDER=true python -m scripts.seed_mock_data   # optional demo data
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

**Tests**

```bash
cd backend
pip install -r requirements.txt
# create a Postgres database named instaopt_test (tests use JSONB columns,
# so SQLite is not supported)
pytest
```

182 tests cover image-metric extraction, normalization math, engagement
calculations, recommendation rules, hashtag analysis, audience timezone
weighting, caption-feature bucketing, caption generation on both model
providers, both Instagram
providers, and the full API (auth, account connect/import, dashboard,
OAuth callback security, upload → analyze → optimize).

The suite **drops every table**, so `conftest.py` forces `DATABASE_URL` to
a test database, overriding whatever is in the environment, and refuses to
run if the target database name doesn't contain `test`. Override the
target with `TEST_DATABASE_URL`, never `DATABASE_URL`.

## Core user flow

1. Register/log in (or skip this entirely with
   [single-user mode](#single-user-mode)).
2. Connect an Instagram account with **Connect Instagram**, which runs the
   real Meta OAuth flow. Instagram is never scraped.
3. Import historical posts (post ID, timestamp, media type, caption, media
   URL, likes/comments/saves/shares, reach, impressions, profile visits,
   follower count at posting time).
4. View the dashboard: overview stats, best-performing posts, performance by
   day of week / hour of day, carousel vs. single-image vs. video.
5. Upload a new image. It's analyzed for measurable visual properties
   (brightness, contrast, saturation, sharpness, highlight/shadow clipping,
   dominant colors, face detection, subject placement, negative space).
6. Review rule-based recommendations (e.g. "consider a 4:5 crop", "highlights
   appear clipped", "darker than your historically stronger posts").
7. Generate an optimized version under **Artwork Integrity mode** (on by
   default) and compare before/after with the exact adjustment values used.
8. Review the heuristic score report (image readiness, timing opportunity,
   historical similarity, overall readiness) — every score comes with a
   plain-language explanation of how it was computed.
9. Optionally generate caption suggestions in the artist's own voice.
10. Review audience timezones, caption habits, and hashtag usage on the
    dashboard — all derived from the account's own data.

## Instagram integration

`app/services/instagram/base.py` defines the `InstagramProvider` interface
(`authenticate`, `get_account`, `get_media`, `get_media_insights`,
`get_account_insights`). Two implementations exist, and both are usable:

- **`MetaInstagramProvider`** — the real Instagram Graph API integration,
  using the **Instagram API with Instagram Login** flow. This is what the
  **"Connect Instagram"** button uses, and the only provider reachable
  from the UI. Instagram is never scraped; only documented API endpoints
  are called.
- **`MockInstagramProvider`** — generates deterministic, realistic
  historical post data locally (60 posts per account, varied media types,
  engagement patterns that vary by day/hour so the analytics layer has
  real patterns to find). No network calls, no credentials. It exists for
  tests and local development, is gated behind `ENABLE_MOCK_PROVIDER`, and
  has no button in the UI.

### Connecting a real Instagram account

**Prerequisites**

1. An **Instagram professional account** (Creator or Business). To check:
   Instagram app → profile → ☰ → *Settings and privacy* → look for the
   *For professionals* section. If **Insights** appears on your profile,
   you're professional.
2. A **Meta app**: developers.facebook.com → *My Apps* → *Create App* →
   **Other** → **Business**. Then *Add products* → **Instagram** → **API
   setup with Instagram login**.
3. Copy the **Instagram App ID** and **Instagram App Secret** from that
   section into `META_APP_ID` / `META_APP_SECRET`. These are **not** the
   Facebook App ID/Secret on the main settings page — using those produces
   a confusing "Invalid platform app" error, so check this first if
   authentication fails.
4. **Permissions and features → add `instagram_business_manage_insights`.**
   The console's "Add all required permissions" button covers only
   basic/comments/messages. Without the insights permission, OAuth still
   succeeds and posts still import, but every metric returns empty — which
   presents as an app bug rather than a missing permission.
5. Add your Instagram account under the token-generation step (assign it
   the **Instagram Tester** role in the Roles tab first, and accept the
   invite from that Instagram account).
6. Register your redirect URI under **Set up Instagram business login**.

Webhooks and App Review are not needed: this app never receives webhooks,
and a development-mode app serves accounts holding a role on it without
review.

**Redirect URI.** Must be HTTPS; Instagram rejects `http://localhost`. For
local development, tunnel the backend and register that URL:

```bash
cloudflared tunnel --url http://localhost:8000
# then set, in backend/.env:
# META_REDIRECT_URI=https://<your-tunnel>.trycloudflare.com/api/v1/accounts/meta/callback
```

The same value must be registered in the Meta app settings.

**App Review is not required to test with your own account.** While the
Meta app is in development mode, the Instagram accounts you add to it get
full permissions immediately. App Review and Business Verification only
become necessary to serve accounts you don't control.

**OAuth flow.** `GET /accounts/meta/authorize-url` returns the consent URL
(carrying a short-lived signed `state` token identifying the user);
Instagram redirects back to `GET /accounts/meta/callback`, which exchanges
the code for a long-lived (~60 day) token, stores the account, and bounces
the browser to `/settings`. Long-lived tokens can be extended before
expiry via `MetaInstagramProvider.refresh_long_lived_token()`; once
expired, the user must reconnect.

`POST /accounts/connect` is the direct, non-OAuth path, used by the mock
provider and by tests. It rejects `provider: "mock"` unless
`ENABLE_MOCK_PROVIDER` is set, so synthetic posts can never reach a real
deployment's dashboard by accident. `INSTAGRAM_PROVIDER` only supplies its
default provider name; accounts connected through OAuth are stored as
`meta` and always use the real API.

## Artwork Integrity mode

On by default. When generating an optimized image, only these operations
are ever applied, and each is clamped to a mild, non-destructive range:
exposure, white balance, contrast, highlight/shadow recovery, mild
saturation correction, sharpening, resize, crop, and small-angle
perspective/level correction. It never repaints any region, alters local
shapes or faces, adds/removes objects, or changes composition beyond
cropping. See `app/services/image_processing/optimizer.py`.

## Caption suggestions & hashtag insight

Two assistive features, both built to the same rule as the scores: they
describe and suggest, they never predict.

**Caption suggestions** (post detail page) send the image and a sample of
the artist's own past captions to a vision model, and return three options
in that artist's voice. The model is instructed never to promise reach or
likes, never to use engagement bait ("double tap if…", "save this"), and
never to invent facts about the work.

Either Anthropic or OpenAI can serve this, selected with
`CAPTION_PROVIDER` in `backend/.env`:

| `CAPTION_PROVIDER` | Key | Model setting |
| --- | --- | --- |
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `CAPTION_MODEL` |
| `openai` | `OPENAI_API_KEY` | `OPENAI_CAPTION_MODEL` |

Only the selected provider's key is needed. Both paths send the same
prompt and the same response schema, so the rest of the app cannot tell
which one answered; the model that actually wrote each caption is stored
on the row, so switching providers does not relabel old suggestions. The
model must be vision-capable — the prompt sends the image itself. Without
a key the endpoint returns a clear "not configured" message and nothing
else in the app is affected.

Both vendor SDKs are imported lazily and their errors are translated into
`CaptionProviderError` inside the caption service, so no route imports a
vendor SDK and the unused package can be removed from a slim deployment.

**Audience timing** (dashboard) uses Meta's `follower_demographics`
insight to map followers to countries, then reports what fraction of them
are in their waking hours at each posting time, translated into your own
local clock. It deliberately stops there: it does not claim that posting
when more people are awake produces more engagement, only that a given
hour reaches more or fewer waking followers — a fact about timezones, not
a prediction about behaviour. Your own historical engagement stays a
separate signal. Demographics refresh automatically on import, or via
`POST /accounts/{id}/sync-demographics`. Meta withholds the breakdown
below 100 followers, and the panel says so rather than guessing.

**Caption habits** (dashboard) buckets your own captions by structural
traits — length, whether they ask a question, emoji use, single vs.
multi-line, opening-line length — and compares each group against your
median. A trait only appears when at least two of its groups clear the
minimum sample, so there is always something to compare against rather
than a lone number. Buckets rather than continuous correlations, because
an artist has tens of posts, not thousands.

**Hashtag insight** (dashboard) groups the account's own posts by the
hashtags they carry and reports each tag's average engagement against the
account's median. Tags used on fewer than three posts are listed but get
no average -- one post is noise. Every response carries an explicit
caveat that these are correlations, not causes: the image, caption, and
timing all varied too, and Instagram exposes no per-hashtag attribution.
There is deliberately no "recommended hashtags to grow" feature, because
nothing in the available data would support one.

## Single-user mode

For a personal deployment, `SINGLE_USER_MODE=true` in `backend/.env`
removes the login screen: every request resolves to one owner account.
Leave `SINGLE_USER_EMAIL` blank and it adopts the oldest existing
account, so an already-running deployment keeps its connected Instagram
account and imported history.

Note the corollary: on a deployment that was ever seeded with demo data,
the oldest account *is* the demo user, so single-user mode adopts it and
the dashboard opens full of synthetic posts. Clear it with
`python -m scripts.purge_mock_data --user` — with no accounts left, the
next request creates a fresh `owner@example.com` instead.

**This is not access control.** It makes every visitor the owner, and the
upload endpoint accepts files from anyone who can reach it. Only enable
it where the deployment is restricted at the network layer — an IP
allowlist, firewall, HTTP basic auth on the proxy, or a VPN. The backend
logs a warning at startup whenever the flag is on. It is off by default
and every endpoint still enforces authentication when it is.

## Scoring philosophy

Every score in Aperture (`app/services/recommendations/scoring.py`) is an
explicit, explainable heuristic — a fixed formula over measurable inputs,
with a plain-language explanation returned alongside every number. None of
it is a machine-learned prediction, and the product never says "you will
get X likes." Preferred language throughout the UI: *"this post appears
more similar to historically strong posts on this account."*

- **Image readiness (0–100)** — starts at 100, subtracts points for
  measurable technical issues (clipped highlights/shadows, low contrast,
  low sharpness, extreme brightness).
- **Timing opportunity (0–100)** — compares the current day/hour against
  this account's own historical average engagement for that bucket.
- **Historical similarity (0–100)** — compares the image's crop against
  Instagram's tallest standard feed ratio, and compares this account's past
  performance for the assumed media type against its own median. (v0.1
  does not re-analyze the pixels of historical posts — see Limitations.)
- **Overall readiness (0–100)** — a weighted average of the three above.

When there isn't enough historical data (fewer than 5–10 posts, depending
on the calculation), the UI shows **"Not enough historical data yet"**
instead of a misleading number.

## Data model

`User`, `InstagramAccount`, `InstagramPost`, `InstagramPostMetric`,
`UploadedImage`, `ImageAnalysis`, `ImageVariant`, `Recommendation` are the
core v0.1 tables. Four additional tables exist as **empty placeholders** for
features explicitly out of scope for this MVP, so they can be added later
without a schema redesign: `PredictionScore` (future ML model output),
`GeneratedCaption` (future AI captions), `ScheduledPost` (future
publishing), `PostOutcome` (future predicted-vs-actual tracking),
`Experiment`/`ExperimentVariant` (future A/B testing).

## Security notes

- Uploaded files are validated by content-type and size (20MB default) and
  stored under randomly generated UUID filenames — the original filename is
  never used as a path.
- Auth tokens (`access_token`) live in dedicated columns on
  `InstagramAccount`, separate from ordinary profile fields, so they can be
  encrypted/rotated independently later.
- No Instagram or Meta credentials are stored in source control — `.env` is
  git-ignored; only `.env.example` files (placeholder values) are committed.
- Passwords are hashed with bcrypt; API auth uses short-lived signed JWTs.

## Known limitations (v0.1)

- **Instagram publishing is not implemented.** The Meta integration reads
  posts and insights only; nothing is ever published to Instagram.
- **Timezone offsets are approximate.** Countries map to a single
  standard UTC offset; daylight saving is ignored (up to an hour of
  drift) and multi-zone countries like the US use their most populous
  zone. The panel states this.
- **No historical follower counts.** Meta's API exposes only the *current*
  follower count, so real imported posts are all stamped with today's
  figure. Follower-normalized comparisons across a long history are
  therefore approximate for back-dated posts. (The mock provider does
  simulate follower growth, so demo data doesn't show this.)
- **Insights coverage varies.** Posts published before the account became
  professional, or older than Meta's insights window, import with metrics
  missing; those posts are kept but contribute nothing to engagement
  stats.
- **Meta token refresh is manual.** `refresh_long_lived_token()` exists
  but nothing calls it on a schedule yet, so a token left unused for ~60
  days expires and the account must be reconnected. A background refresh
  job is the natural fix.
- The Meta integration is covered by tests with mocked HTTP; it has not
  been exercised against live Meta credentials.
- **Caption suggestions cost money per call** and are not cached — each
  press of "Suggest captions" is a fresh model API request. Fine at
  personal scale; add caching before exposing it to many users.
- **Caption quality depends on having past captions.** With no connected
  account, the model infers a generic artist voice rather than yours.
- No billing/subscription system.
- No ML/prediction model — all recommendations and scores are rule-based
  heuristics, by design.
- "Historical similarity" does not re-analyze the pixels of previously
  posted images (only their metadata), since the MVP does not re-fetch and
  process historical media.
- Single-tenant-style auth (no OAuth/social login, no password reset flow).
- No background job queue — image analysis/optimization run synchronously
  in the request. Fine for MVP-sized images; would need a queue for scale.
- Frontend pins Next.js 14.2.x rather than the current major version, to
  avoid an App Router migration inside this MVP; see `frontend/package.json`.

## Recommended next 5 development tasks

1. Add a scheduled job that refreshes long-lived Meta tokens before they
   expire, and surfaces "reconnect needed" in the UI when one lapses.
2. Add a background job queue (e.g. Celery/RQ) for image analysis,
   optimization, and Instagram imports — a 60-post import currently makes
   one insights call per post inside the request.
3. Cache caption suggestions per image so re-opening a post page does not
   re-bill an API call, and surface the `accepted` flag when a user copies
   one (already stored, nothing reads it yet).
4. Build the first real prediction model using `PredictionScore` +
   `PostOutcome` (already schema-ready) once enough real outcome data
   exists, and surface it alongside — never in place of — the heuristic
   scores.
5. Add scheduled posting (`ScheduledPost` is schema-ready) once Meta
   publishing is implemented, with explicit user confirmation before any
   post goes live.
