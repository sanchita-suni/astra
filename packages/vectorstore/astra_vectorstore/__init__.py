"""FAISS + sentence-transformers wrapper.

Used by:
- analyst_crew (Day 3) — semantic overlap between user skills and opportunity requirements
- scrapers (Day 2) — embed every new opportunity at ingest time

Lazy-loads the embedding model to keep import cheap. The default model
(`all-MiniLM-L6-v2`) is ~80MB and downloads on first use; it's pre-pulled by
the docker compose `ollama-pull` service so cold-start isn't a Day 3 surprise.
"""

from astra_vectorstore.embedder import Embedder, get_default_embedder
from astra_vectorstore.store import OpportunityVectorStore

__all__ = ["Embedder", "OpportunityVectorStore", "get_default_embedder"]
