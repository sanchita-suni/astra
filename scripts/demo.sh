#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Astra — full demo script
#
# Usage:
#   bash scripts/demo.sh          # full stack (Docker + API + frontend)
#   bash scripts/demo.sh --quick  # API + frontend only (no Docker)
#   bash scripts/demo.sh --test   # run all 66 tests only
#
# Prerequisites:
#   - uv (https://docs.astral.sh/uv/)
#   - pnpm (https://pnpm.io/)
#   - Docker Desktop (for --full mode)
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[astra]${NC} $*"; }
ok()    { echo -e "${GREEN}[astra]${NC} $*"; }
fail()  { echo -e "${RED}[astra]${NC} $*"; exit 1; }

MODE="${1:-}"

# ─────────────────────────────────────────────────────────────────────
# 0. Environment
# ─────────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  info "Creating .env from infra/.env.example"
  cp infra/.env.example .env
fi

# ─────────────────────────────────────────────────────────────────────
# 1. Python dependencies
# ─────────────────────────────────────────────────────────────────────
info "Syncing Python workspace (uv sync --all-packages) ..."
uv sync --all-packages --quiet 2>/dev/null || uv sync --all-packages

# Ensure pytest is in the venv
uv pip install pytest pytest-asyncio iniconfig --python .venv/Scripts/python.exe --quiet 2>/dev/null || true
uv pip install pytest pytest-asyncio iniconfig --python .venv/bin/python --quiet 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────────
# 2. Tests
# ─────────────────────────────────────────────────────────────────────
if [ "$MODE" = "--test" ]; then
  info "Running full test suite ..."
  .venv/Scripts/python.exe -m pytest 2>/dev/null || .venv/bin/python -m pytest
  ok "All tests passed."
  exit 0
fi

info "Running tests first ..."
if .venv/Scripts/python.exe -m pytest -q 2>/dev/null || .venv/bin/python -m pytest -q 2>/dev/null; then
  ok "Tests passed."
else
  fail "Tests failed — fix before running the demo."
fi

# ─────────────────────────────────────────────────────────────────────
# 3. Docker (skip with --quick)
# ─────────────────────────────────────────────────────────────────────
if [ "$MODE" != "--quick" ]; then
  if command -v docker &>/dev/null; then
    info "Starting Docker services (Postgres, Redis, Ollama) ..."
    docker compose -f infra/docker-compose.yml up -d --wait 2>/dev/null || \
      docker-compose -f infra/docker-compose.yml up -d
    ok "Docker services up."

    info "Running Alembic migration ..."
    cd apps/api
    .venv/../../.venv/Scripts/python.exe -m alembic upgrade head 2>/dev/null || \
      ../../.venv/bin/python -m alembic upgrade head 2>/dev/null || \
      info "Alembic migration skipped (DB may not be ready yet — try manually)."
    cd "$ROOT"
  else
    info "Docker not found — skipping. The API will serve the demo fixture without a DB."
  fi
fi

# ─────────────────────────────────────────────────────────────────────
# 4. Frontend deps
# ─────────────────────────────────────────────────────────────────────
info "Installing frontend dependencies ..."
cd apps/web
pnpm install --silent 2>/dev/null || pnpm install
cd "$ROOT"

# ─────────────────────────────────────────────────────────────────────
# 5. Start API + Frontend
# ─────────────────────────────────────────────────────────────────────
info "Starting API on :8000 ..."
(.venv/Scripts/python.exe -m uvicorn astra_api.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api 2>/dev/null || \
 .venv/bin/python -m uvicorn astra_api.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api) &
API_PID=$!

# Give the API a moment to boot
sleep 2

info "Starting Next.js frontend on :3000 ..."
cd apps/web
pnpm dev &
WEB_PID=$!
cd "$ROOT"

ok "═══════════════════════════════════════════════════════"
ok " Astra is running!"
ok ""
ok " API:       http://localhost:8000"
ok " API docs:  http://localhost:8000/docs"
ok " Frontend:  http://localhost:3000"
ok " Demo opp:  http://localhost:3000/opportunity/demo"
ok " Rehearsal: http://localhost:3000/opportunity/demo/rehearsal"
ok ""
ok " Press Ctrl+C to stop."
ok "═══════════════════════════════════════════════════════"

cleanup() {
  info "Shutting down ..."
  kill $API_PID 2>/dev/null || true
  kill $WEB_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
