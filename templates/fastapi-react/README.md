# {opportunity_title}

Scaffolded by **Astra** for the {organization} hackathon. FastAPI backend +
Vite/React frontend split into two packages so you can deploy each
independently. Read [BRIEF.md](BRIEF.md) for what you're building.

## Quick start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev    # http://localhost:5173
```

## Layout

- `backend/main.py` — FastAPI app with `/health` and a sample CRUD endpoint
- `backend/requirements.txt` — pinned API stack
- `frontend/src/App.tsx` — Vite/React app that hits the backend
- `BRIEF.md` — Astra's per-opportunity brief and Day-1 task list
