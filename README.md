# Astra — Opportunity, On-Target

> Multi-agent AI hackathon co-pilot. Doesn't just *list* hackathons — closes your skill gap, scaffolds your starter repo, and rehearses you for demo day.

## What makes Astra different

Astra is not another Devpost feed. Three differentiators:

1. **Bridge-to-Build (USP A)** — when you commit to a hackathon, Astra picks one of 4 starter templates (`python-ml`, `nextjs-fullstack`, `fastapi-react`, `generic-python`), writes a `BRIEF.md` with the opportunity's requirements + a Day-1 task list, and creates a real GitHub repo. First commit is ready before you open your editor.
2. **Dry-Run Demo Day (USP B)** — three AI judge personas (Industry / Academic / VC) score your pitch on feasibility, novelty, market fit, and polish. Get a rubric + feedback before submission day.
3. **Proof-of-Work Vault (USP D)** — your GitHub repos auto-narrated into a one-pager portfolio. On apply, Astra picks the 3 most relevant proofs.

Plus the table-stakes: a personalized opportunity feed, a 7-day "bridge roadmap" that actually closes the skill gap, and a deadman switch calibrated to *your* commit velocity.

## Tech stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.11), SQLAlchemy 2.0, asyncpg, Alembic |
| Agents | CrewAI 0.7x, LiteLLM, Ollama (llama3.1:8b-instruct-q4_K_M) |
| Scrapers | BeautifulSoup4 + dateparser (Scrapy reserved for live targets) |
| ML | sentence-transformers (all-MiniLM-L6-v2), FAISS |
| Frontend | Next.js 14 (App Router), Tailwind CSS |
| Infra | Docker Compose (Postgres 16, Redis 7, Ollama), uv workspace |

100% open source, 0 paid API keys required.

## Monorepo layout

```
apps/
  api/        FastAPI service — the contract surface
  agents/     CrewAI crews (scout, analyst, roadmap, vault, builder, judge)
  scrapers/   Devpost parser + normalization pipeline
  web/        Next.js dashboard + rehearsal UI
packages/
  schemas/         Pydantic v2 models — SINGLE SOURCE OF TRUTH
  core/            trust score, deadman switch math, proof-of-work
  vectorstore/     FAISS wrapper + sentence-transformers embedder
  github_client/   PyGithub wrapper (vault + scaffolder + trust)
templates/         Bridge-to-Build starter repos (4 templates)
infra/             docker-compose.yml, .env.example
scripts/           demo.sh
docs/              sample_digest.json (north-star fixture)
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python workspace manager)
- [pnpm](https://pnpm.io/) (frontend package manager)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres + Ollama, optional)
- Node.js 20+
- Python 3.11 or 3.12

## Quickstart

### 1. Clone and set up environment

```bash
git clone https://github.com/sanchita-suni/astra.git
cd astra
cp infra/.env.example .env
```

### 2. Install Python workspace

```bash
uv sync --all-packages
```

### 3. Install frontend deps

```bash
cd apps/web && pnpm install && cd ../..
```

### 4. Run the test suite (66 tests, no Docker needed)

```bash
# On Windows (Git Bash):
.venv/Scripts/python.exe -m pytest

# On macOS/Linux:
.venv/bin/python -m pytest
```

You should see: **66 passed**.

### 5. Start the API (works without Docker — serves the demo fixture)

```bash
# Windows:
.venv/Scripts/python.exe -m uvicorn astra_api.main:app --reload --app-dir apps/api --port 8000

# macOS/Linux:
.venv/bin/python -m uvicorn astra_api.main:app --reload --app-dir apps/api --port 8000
```

Verify: `curl http://localhost:8000/health`

### 6. Start the frontend (in a separate terminal)

```bash
cd apps/web && pnpm dev
```

### 7. Open the app

- **Home**: http://localhost:3000
- **Demo opportunity**: http://localhost:3000/opportunity/demo
- **Rehearsal**: http://localhost:3000/opportunity/demo/rehearsal

### One-liner demo script

```bash
bash scripts/demo.sh          # full stack (tests + Docker + API + frontend)
bash scripts/demo.sh --quick  # skip Docker (API + frontend only)
bash scripts/demo.sh --test   # tests only
```

## Optional: Docker services (Postgres + Ollama)

If you want the database path and LLM-powered narrations:

```bash
# Start services
docker compose -f infra/docker-compose.yml up -d

# Wait for Ollama to pull the model (~4GB first time)
docker compose -f infra/docker-compose.yml logs -f ollama-pull

# Run the Alembic migration
cd apps/api
../../.venv/Scripts/python.exe -m alembic upgrade head   # Windows
../../.venv/bin/python -m alembic upgrade head            # macOS/Linux
cd ../..
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/opportunities` | List opportunities (DB or demo fixture) |
| GET | `/opportunities/{id}` | Single opportunity (`demo` = fixture) |
| POST | `/opportunities` | Idempotent upsert |
| POST | `/opportunities/{id}/scaffold` | USP A — scaffold a starter repo |
| POST | `/opportunities/{id}/dry-run` | USP B — 3-judge rubric |
| GET | `/users/{login}/vault` | USP D — narrated portfolio |

Interactive docs at http://localhost:8000/docs

### Try the API from the command line

```bash
# Health check
curl http://localhost:8000/health

# Get the demo opportunity
curl http://localhost:8000/opportunities/demo | python -m json.tool

# Scaffold a starter repo (dry run)
curl -X POST "http://localhost:8000/opportunities/demo/scaffold?dry_run=true&use_llm=false" | python -m json.tool

# Run demo-day rehearsal
curl -X POST "http://localhost:8000/opportunities/demo/dry-run?use_llm=false" \
  -H "Content-Type: application/json" \
  -d '{"pitch": "We are building a real-time pothole detector that runs on a Raspberry Pi with a camera. The user is city public-works departments that want to automate road surveys."}' \
  | python -m json.tool
```

## Test suite breakdown

| Suite | Tests | What it covers |
|-------|------:|----------------|
| `packages/schemas/tests/` | 7 | Contract lock — fixture round-trips through Pydantic |
| `packages/core/tests/` | 7 | Trust score math + deadman switch math |
| `apps/agents/tests/` | 40 | All 6 crews (scout, analyst, roadmap, vault, builder, judge) deterministic fallbacks |
| `apps/scrapers/tests/` | 12 | Devpost parser + normalizers + stub bridge |
| **Total** | **66** | |

## Architecture decisions

- **Contract-first**: `packages/schemas/` is the single source of truth. Everything else (API, frontend, agents, scrapers) consumes these Pydantic models. TypeScript types are hand-mirrored for Day 1-5, then auto-generated via `pydantic2ts`.
- **Every crew has a deterministic fallback**: CrewAI + Ollama is the polish layer, never the reliability layer. Tests exercise the fallback path only — no LLM, no network, no flakiness.
- **JSONB-first DB**: one `opportunities` table, one `digest` JSONB column. Fields get promoted out of JSONB only when you actually need to index/filter them.
- **Lazy CrewAI imports**: the API process imports crew modules without loading CrewAI's heavy graph. The LLM path is lazy-imported inside `_*_with_llm` helpers, so the API stays fast when the LLM is down.

## Status

Day 5 of 5-day MVP build. All three USPs (Bridge-to-Build, Dry-Run Demo Day, Proof-of-Work Vault) are functional with deterministic fallbacks and LLM upgrade paths.
