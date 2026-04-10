"""Astra FastAPI entry point.

Run with:
    uv run uvicorn astra_api.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env into os.environ BEFORE anything else reads env vars.
# This ensures GitHubClient, Groq, SMTP, etc. all pick up the config
# even when running via `uvicorn --reload`.
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

from astra_api import __version__
from astra_api.routers import admin, auth, opportunities, users
from astra_api.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Day 1: nothing to warm up. Day 2+ will preload FAISS index here.
    yield


app = FastAPI(
    title="Astra API",
    description="Multi-agent AI hackathon co-pilot. Opportunity, On-Target.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(opportunities.router)
app.include_router(users.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — used by docker-compose, Render, and the verification suite."""
    return {"status": "ok", "service": "astra-api", "version": __version__}


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "Astra API",
        "tagline": "Opportunity, On-Target.",
        "docs": "/docs",
        "health": "/health",
    }
