# Astra — Opportunity, On-Target

> Multi-agent AI hackathon co-pilot. Doesn't just *list* hackathons — closes your skill gap, scaffolds your starter repo, and rehearses you for demo day.

## What makes Astra different

Astra is not another Devpost feed. Three differentiators:

1. **Bridge-to-Build** — when you commit to a hackathon, Astra picks one of 4 starter templates (`python-ml`, `nextjs-fullstack`, `fastapi-react`, `generic-python`), writes a `BRIEF.md` with the opportunity's requirements + a Day-1 task list, and creates a real GitHub repo. First commit is ready before you open your editor.
2. **Dry-Run Demo Day** — three AI judge personas (Industry / Academic / VC) score your pitch on feasibility, novelty, market fit, and polish. Get a rubric + feedback before submission day.
3. **Proof-of-Work Vault** — your GitHub repos auto-narrated into a portfolio with a skill heatmap. Shows what you've actually shipped.

Plus: personalized hackathon feed (FAISS semantic matching), 7-day bridge roadmaps with real courses/tutorials, deadman switch calibrated to your commit velocity, resume parsing, and weekly email digests.

## Tech stack

| Layer | Tech |
|-------|------|
| **Backend** | FastAPI (Python 3.11), SQLAlchemy 2.0, asyncpg, Alembic |
| **AI Agents** | CrewAI 0.7x, LiteLLM, Groq (fast cloud LLM) + Ollama (local fallback) |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2), FAISS |
| **Scrapers** | Devpost API, HackerEarth API, MLH, BeautifulSoup4 |
| **Frontend** | Next.js 16 (App Router), Tailwind CSS |
| **Auth** | GitHub OAuth, JWT cookie sessions |
| **Email** | Gmail SMTP (welcome + registration + weekly digest) |
| **DB** | PostgreSQL 16 (local or Neon free tier for production) |
| **Infra** | Docker Compose, uv workspace, Render/Koyeb + Vercel for deploy |

## Monorepo layout

```
apps/
  api/           FastAPI service (27 endpoints)
  agents/        CrewAI crews (scout, analyst, roadmap, vault, builder, judge)
  scrapers/      Devpost, HackerEarth, MLH, Unstop, Hack2Skill scrapers
  web/           Next.js frontend (feed, opportunity detail, profile, onboarding)
packages/
  schemas/       Pydantic v2 models — SINGLE SOURCE OF TRUTH
  core/          trust score, deadman switch, proof-of-work, resume parser, feed ranker
  vectorstore/   FAISS wrapper + sentence-transformers embedder
  github_client/ PyGithub wrapper (vault + scaffolder + trust score)
templates/       Bridge-to-Build starter repos (4 templates)
scripts/         scrape_all.py, demo.sh
infra/           docker-compose.yml, .env.example
docs/            sample_digest.json (canonical fixture)
```

---

## Prerequisites

Install these before starting:

| Tool | Version | Install |
|------|---------|---------|
| **Python** | 3.11 or 3.12 | https://python.org/downloads/ |
| **uv** | latest | `pip install uv` or https://docs.astral.sh/uv/getting-started/installation/ |
| **Node.js** | 20+ | https://nodejs.org/ |
| **pnpm** | 9+ | `npm install -g pnpm` |
| **Docker Desktop** | latest | https://docker.com/products/docker-desktop/ (optional, for local Postgres) |
| **Git** | latest | https://git-scm.com/ |

---

## Step-by-step setup (local development)

### 1. Clone the repo

```bash
git clone https://github.com/sanchita-suni/astra.git
cd astra
```

### 2. Create your environment file

```bash
cp infra/.env.example .env
```

Now open `.env` in your editor and fill in these values:

```env
# REQUIRED — get a free key at https://console.groq.com/keys (no credit card)
GROQ_API_KEY=gsk_your_key_here

# REQUIRED — Postgres connection
# Option A: Local Docker (see step 5 below)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/astra
# Option B: Neon free cloud Postgres (see "Cloud Postgres" section below)
# DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/astra?sslmode=require

# REQUIRED for login — create at https://github.com/settings/developers
# Set callback URL to: http://localhost:8000/auth/github/callback
GITHUB_CLIENT_ID=your_oauth_client_id
GITHUB_CLIENT_SECRET=your_oauth_client_secret

# REQUIRED for vault + scaffold — create at https://github.com/settings/tokens
# Scopes needed: repo, read:user
GITHUB_TOKEN=ghp_your_token_here

# OPTIONAL — for email notifications
# Enable 2FA on your Gmail, then get an App Password at:
# https://myaccount.google.com/apppasswords
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SMTP_FROM=your-email@gmail.com
```

### 3. Install Python dependencies

```bash
uv sync --all-packages
```

This installs all workspace packages (schemas, core, agents, api, scrapers, etc.) into `.venv/`.

Then install test dependencies:

```bash
# Windows
uv pip install pytest pytest-asyncio iniconfig python-jose pypdf --python .venv/Scripts/python.exe

# macOS/Linux
uv pip install pytest pytest-asyncio iniconfig python-jose pypdf --python .venv/bin/python
```

### 4. Install frontend dependencies

```bash
cd apps/web
pnpm install
cd ../..
```

### 5. Set up the database

You have two options:

#### Option A: Local Postgres via Docker (recommended for development)

```bash
# Start Postgres + Redis + Ollama
docker compose -f infra/docker-compose.yml up -d

# Wait for Postgres to be ready (~10 seconds)
# Then create the database (if using Docker for the first time):
docker exec -it astra-postgres psql -U astra -c "SELECT 1"
```

If you already have Postgres installed locally (not Docker):
```bash
# Create the astra database
psql -U postgres -c "CREATE DATABASE astra"
```

> **Note:** If your local Postgres uses different credentials, update `DATABASE_URL` in `.env`:
> `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/astra`

#### Option B: Neon cloud Postgres (free, no install)

1. Go to https://neon.tech and sign up (free, no credit card)
2. Create a project called `astra`
3. Copy the connection string and add `+asyncpg` after `postgresql`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/astra?sslmode=require
   ```
4. Paste into your `.env`

#### Run database migrations

```bash
cd apps/api

# Windows
../../.venv/Scripts/python.exe -m alembic upgrade head

# macOS/Linux
../../.venv/bin/python -m alembic upgrade head

cd ../..
```

You should see:
```
Running upgrade  -> 0001_initial
Running upgrade 0001_initial -> 0002_users
Running upgrade 0002_users -> 0003_registrations
```

### 6. Seed real hackathon data

```bash
# Windows
.venv/Scripts/python.exe scripts/scrape_all.py

# macOS/Linux
.venv/bin/python scripts/scrape_all.py
```

This fetches ~50 live hackathons from Devpost + HackerEarth and stores them in Postgres.

### 7. Run the test suite

```bash
# Windows
.venv/Scripts/python.exe -m pytest

# macOS/Linux
.venv/bin/python -m pytest
```

Expected: **66 passed**.

### 8. Start the API

Open a terminal:

```bash
# Windows
.venv/Scripts/python.exe -m uvicorn astra_api.main:app --reload --app-dir apps/api --port 8000

# macOS/Linux
.venv/bin/python -m uvicorn astra_api.main:app --reload --app-dir apps/api --port 8000
```

Verify: open http://localhost:8000/health — should return `{"status": "ok"}`.

### 9. Start the frontend

Open a **second** terminal:

```bash
cd apps/web
pnpm dev
```

### 10. Open the app

| Page | URL |
|------|-----|
| **Home (hackathon feed)** | http://localhost:3000 |
| **Opportunity detail** | Click any hackathon from the feed |
| **Demo day rehearsal** | Click "Rehearse demo day" on any opportunity |
| **Profile + skill heatmap** | http://localhost:3000/profile/your-github-username |
| **Onboarding questionnaire** | http://localhost:3000/onboarding |
| **Login** | Click "Sign in with GitHub" in the nav bar |
| **API docs (Swagger)** | http://localhost:8000/docs |

---

## Setting up GitHub OAuth (required for login)

1. Go to https://github.com/settings/developers
2. Click **"New OAuth App"**
3. Fill in:
   - **Application name**: `Astra`
   - **Homepage URL**: `http://localhost:3000`
   - **Authorization callback URL**: `http://localhost:8000/auth/github/callback`
4. Click **Register application**
5. Copy the **Client ID** and generate a **Client Secret**
6. Add both to your `.env`:
   ```
   GITHUB_CLIENT_ID=Ov23li...
   GITHUB_CLIENT_SECRET=98e521...
   ```
7. Restart the API

---

## Refreshing hackathon data

Hackathons are scraped from Devpost + HackerEarth on demand. To refresh:

**From the command line:**
```bash
.venv/Scripts/python.exe scripts/scrape_all.py    # Windows
.venv/bin/python scripts/scrape_all.py             # macOS/Linux
```

**From the API (while running):**
```bash
curl -X POST http://localhost:8000/admin/scrape
```

**From Swagger UI:**
Open http://localhost:8000/docs → find `POST /admin/scrape` → click Execute.

---

## API endpoints (27 total)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | Liveness probe |
| GET | `/` | No | Service info |
| **Opportunities** | | | |
| GET | `/opportunities` | Optional | List all (personalized if logged in) |
| GET | `/opportunities/{id}` | Optional | Single opportunity (personalized if logged in) |
| POST | `/opportunities` | No | Upsert opportunity |
| POST | `/opportunities/{id}/scaffold` | No | Bridge-to-Build — scaffold a starter repo |
| POST | `/opportunities/{id}/dry-run` | No | Demo Day — 3-judge rubric |
| POST | `/opportunities/{id}/register` | Yes | Register interest in a hackathon |
| DELETE | `/opportunities/{id}/register` | Yes | Unregister from a hackathon |
| GET | `/opportunities/me/registered` | Yes | List your registered hackathons |
| **Auth** | | | |
| GET | `/auth/github` | No | Start GitHub OAuth flow |
| GET | `/auth/github/callback` | No | OAuth callback (sets session cookie) |
| GET | `/auth/me` | No | Get current user (null if not logged in) |
| POST | `/auth/logout` | No | Clear session |
| **Users** | | | |
| GET | `/users/{login}/vault` | No | Proof-of-Work Vault (narrated portfolio) |
| GET | `/users/me/profile` | Yes | Your profile |
| GET | `/users/{login}/profile` | No | Any user's profile |
| PUT | `/users/me/questionnaire` | Yes | Save onboarding answers |
| POST | `/users/me/resume` | Yes | Upload PDF resume for skill extraction |
| GET | `/users/me/feed` | Yes | Personalized opportunity feed |
| **Admin** | | | |
| POST | `/admin/scrape` | No | Trigger fresh scrape from all sources |
| GET | `/admin/stats` | No | DB stats (counts by source/type) |
| POST | `/admin/send-digest` | No | Send weekly digest email to all users |

---

## Deployment (free, no credit card)

### Backend: Koyeb

1. Sign up at https://www.koyeb.com with GitHub (free tier, no card)
2. Create App → GitHub → select `sanchita-suni/astra`
3. Builder: **Dockerfile**, path: `apps/api/Dockerfile`, port: `8000`
4. Add environment variables from your `.env`
5. Deploy

### Database: Neon

1. Sign up at https://neon.tech (free, no card)
2. Create project `astra`
3. Copy connection string → add `+asyncpg` → use as `DATABASE_URL`

### Frontend: Vercel

1. Sign up at https://vercel.com with GitHub (free, no card)
2. Import `sanchita-suni/astra`
3. Root directory: `apps/web`
4. Add env var: `NEXT_PUBLIC_API_BASE_URL` = your Koyeb API URL
5. Deploy

### After deploying: update OAuth

Go to GitHub → Developer Settings → your OAuth app:
- **Homepage URL**: your Vercel URL
- **Callback URL**: `https://your-koyeb-api.koyeb.app/auth/github/callback`

Update on Koyeb:
- `FRONTEND_URL` = your Vercel URL
- `GITHUB_CALLBACK_URL` = `https://your-koyeb-api.koyeb.app/auth/github/callback`

---

## Architecture

```
User → Next.js (Vercel) → FastAPI (Koyeb) → PostgreSQL (Neon)
                                ↓
                          CrewAI Agents → Groq LLM (cloud, ~1s)
                                ↓            ↘ Ollama (local fallback)
                          FAISS Embeddings
                                ↓
                     Devpost / HackerEarth APIs
```

**Key design decisions:**
- **Contract-first**: `packages/schemas/` is the single source of truth. Everything consumes Pydantic v2 models.
- **Every AI crew has a deterministic fallback**: LLM is the polish layer, never the reliability layer. If Groq is down, the app still works.
- **Per-user scoring at request time**: opportunities are stored neutrally in Postgres. Fit scores, skill gaps, and roadmaps are computed per-user when they load the page.
- **FAISS semantic matching**: the feed ranker embeds user skills + opportunity requirements via sentence-transformers and uses cosine similarity — catches "PyTorch" ≈ "Deep Learning".

---

## Test suite

```bash
.venv/Scripts/python.exe -m pytest -v    # Windows
.venv/bin/python -m pytest -v            # macOS/Linux
```

| Suite | Tests | What it covers |
|-------|------:|----------------|
| `packages/schemas/tests/` | 7 | Contract lock — fixture round-trips through Pydantic |
| `packages/core/tests/` | 7 | Trust score + deadman switch math |
| `apps/agents/tests/` | 40 | All 6 crews deterministic fallbacks |
| `apps/scrapers/tests/` | 12 | Devpost parser + normalizers |
| **Total** | **66** | |

---

## License

MIT
