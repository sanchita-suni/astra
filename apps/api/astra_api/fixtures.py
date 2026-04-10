"""Lazy-loaded canonical fixture for Day 1 / demo mode.

Until the scrapers and DB are wired (Day 2+), the API serves the canonical
sample digest from `docs/sample_digest.json` for the magic ID `demo`. This is
the same fixture the contract lock test validates against.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from astra_schemas import Opportunity

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "docs" / "sample_digest.json"


@lru_cache(maxsize=1)
def load_demo_opportunity() -> Opportunity:
    """Read and validate the canonical fixture once, cache for the process lifetime."""
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(
            f"Canonical fixture missing at {FIXTURE_PATH} — Day 1 contract lock is broken."
        )
    return Opportunity.model_validate_json(FIXTURE_PATH.read_text(encoding="utf-8"))
