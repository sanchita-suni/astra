"""Sentence-transformers embedder.

Wraps `SentenceTransformer` so the rest of the code never imports it directly.
That gives us one place to swap models, batch sizes, or device selection.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_NAME = os.getenv("ASTRA_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEFAULT_DIM = 384  # all-MiniLM-L6-v2 emits 384-dim vectors


class Embedder:
    """Encode text into a fixed-dim vector using sentence-transformers."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._dim: int | None = None

    def _load(self) -> SentenceTransformer:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # heavy import; lazy

            self._model = SentenceTransformer(self.model_name)
            self._dim = int(self._model.get_sentence_embedding_dimension() or DEFAULT_DIM)
        return self._model

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._load()
        assert self._dim is not None
        return self._dim

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode a list of strings into a (N, dim) float32 array, L2-normalized."""
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")
        model = self._load()
        vecs = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,  # so we can use inner product = cosine similarity
            show_progress_bar=False,
        )
        return vecs.astype("float32")

    def encode_one(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


@lru_cache(maxsize=1)
def get_default_embedder() -> Embedder:
    return Embedder()
