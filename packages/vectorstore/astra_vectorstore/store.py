"""FAISS opportunity vector store.

Each opportunity is embedded from the joined text of its `metadata.title +
organization + raw_requirements`. The index is in-memory; persisted to disk
via `save()` / `load()` so the API can warm up without re-embedding.

We use `IndexFlatIP` (inner product) since our embeddings are L2-normalized,
making inner product == cosine similarity. Flat index is fine until we hit
~50k opportunities; switch to HNSW if/when needed.
"""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np
from pydantic import BaseModel

from astra_schemas import Opportunity
from astra_vectorstore.embedder import Embedder, get_default_embedder


class SearchHit(BaseModel):
    opportunity_id: str
    score: float


class OpportunityVectorStore:
    """In-memory FAISS index keyed by opportunity_id, with disk persistence."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or get_default_embedder()
        self._index: faiss.Index | None = None
        self._ids: list[str] = []

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _ensure_index(self) -> faiss.Index:
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.embedder.dim)
        return self._index

    @staticmethod
    def _opportunity_text(opp: Opportunity) -> str:
        parts = [
            opp.metadata.title,
            opp.metadata.organization,
            " ".join(opp.metadata.raw_requirements),
        ]
        return " | ".join(p for p in parts if p)

    def add(self, opportunities: list[Opportunity]) -> None:
        if not opportunities:
            return
        texts = [self._opportunity_text(o) for o in opportunities]
        vectors = self.embedder.encode(texts)
        index = self._ensure_index()
        index.add(vectors)  # type: ignore[arg-type]
        self._ids.extend(o.opportunity_id for o in opportunities)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        if self._index is None or self._index.ntotal == 0:
            return []
        q = self.embedder.encode_one(query).reshape(1, -1)
        scores, idxs = self._index.search(q, top_k)  # type: ignore[arg-type]
        out: list[SearchHit] = []
        for score, idx in zip(scores[0].tolist(), idxs[0].tolist()):
            if idx < 0 or idx >= len(self._ids):
                continue
            out.append(SearchHit(opportunity_id=self._ids[idx], score=float(score)))
        return out

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._index is None:
            return
        faiss.write_index(self._index, str(path))
        ids_path = path.with_suffix(path.suffix + ".ids")
        ids_path.write_text("\n".join(self._ids), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            return
        self._index = faiss.read_index(str(path))
        ids_path = path.with_suffix(path.suffix + ".ids")
        if ids_path.exists():
            self._ids = [line for line in ids_path.read_text(encoding="utf-8").splitlines() if line]

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return self._index.ntotal if self._index is not None else 0
