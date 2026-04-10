"""Sample FastAPI backend.

Hello-world API with a health probe and an in-memory items list. Replace with
your real domain. The CORS middleware is wide-open for local dev — tighten it
before deploying.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="hackathon-starter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Item(BaseModel):
    id: int
    name: str


_items: list[Item] = [Item(id=1, name="hello"), Item(id=2, name="hackathon")]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/items")
def list_items() -> list[Item]:
    return _items
