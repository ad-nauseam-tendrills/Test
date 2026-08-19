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
      instagram/         # InstagramProvider abstraction (mock + Meta placeholder)
      analytics/         # engagement, normalization, timing calculations
      image_analysis/    # Pillow/OpenCV measurable-property extraction
      image_processing/  # Artwork Integrity optimization engine
      recommendations/   # rule-based recommendations + heuristic scoring
    tests/                # pytest suite (57 tests)
  alembic/                # migrations
  scripts/seed_mock_data.py
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
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local   # optional, only for `npm run dev` outside Docker

docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (docs at http://localhost:8000/docs)
- Postgres: localhost:5432 (user/pass `postgres` / `postgres`, db `instaopt`)

The backend container runs `alembic upgrade head` automatically on startup.

To load a demo account with 60 realistic historical posts:

```bash
docker compose exec backend python -m scripts.seed_mock_data
```

This prints a demo login (`demo@artstudio.example` / `demo12345`). Log in
with those credentials, or register your own account and connect a mock
Instagram account from the dashboard.

## Local development (without Docker)

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL to point at your local Postgres
alembic upgrade head
python -m scripts.seed_mock_data   # optional
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

57 tests cover image-metric extraction, normalization math, engagement
calculations, recommendation rules, the provider abstraction, and the full
API (auth, account connect/import, dashboard, upload → analyze → optimize).

## Core user flow

1. Register/log in.
2. Connect an Instagram account — in this MVP, always the **mock
   provider** (`app/services/instagram/mock_provider.py`), which generates
   realistic, deterministic synthetic post history locally. No real Meta
   credentials are required and Instagram is never scraped.
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

## Instagram integration

`app/services/instagram/base.py` defines the `InstagramProvider` interface
(`authenticate`, `get_account`, `get_media`, `get_media_insights`,
`get_account_insights`). Two implementations exist:

- **`MockInstagramProvider`** — the default. Generates deterministic,
  realistic historical post data locally (60 posts per account, varied
  media types, engagement patterns that vary by day/hour so the analytics
  layer has real patterns to find). No network calls.
- **`MetaInstagramProvider`** — a structural placeholder for the real Meta
  Graph API. It matches the shape of the real integration (OAuth token
  exchange, `/me/media`, insights edges) but every method raises a clear
  `NotImplementedError`/`MetaCredentialsMissingError` rather than silently
  failing. See the module docstring for exactly which Graph API calls to
  implement and where credentials go (`META_APP_ID`, `META_APP_SECRET`,
  `META_REDIRECT_URI` environment variables — never committed to source
  control).

Switch providers via `INSTAGRAM_PROVIDER=mock|meta` in `backend/.env`.

## Artwork Integrity mode

On by default. When generating an optimized image, only these operations
are ever applied, and each is clamped to a mild, non-destructive range:
exposure, white balance, contrast, highlight/shadow recovery, mild
saturation correction, sharpening, resize, crop, and small-angle
perspective/level correction. It never repaints any region, alters local
shapes or faces, adds/removes objects, or changes composition beyond
cropping. See `app/services/image_processing/optimizer.py`.

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

- The Meta Graph API integration is a structural placeholder only —
  real Instagram publishing and OAuth are not implemented.
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

1. Implement the real `MetaInstagramProvider` (OAuth flow + Graph API calls)
   behind the existing abstraction, gated by `INSTAGRAM_PROVIDER=meta`.
2. Add a background job queue (e.g. Celery/RQ) for image analysis and
   optimization so large uploads don't block request threads.
3. Build the first real prediction model using `PredictionScore` +
   `PostOutcome` (already schema-ready) once enough real outcome data
   exists, and surface it alongside — never in place of — the heuristic
   scores.
4. Add scheduled posting (`ScheduledPost` is schema-ready) once Meta
   publishing is implemented, with explicit user confirmation before any
   post goes live.
5. Add account-level settings for notification preferences and a proper
   password-reset / email-verification flow ahead of any public launch.
