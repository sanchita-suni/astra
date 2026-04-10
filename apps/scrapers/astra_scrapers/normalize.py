"""Field normalization helpers for scraper output.

Spiders pull text out of HTML; this module canonicalizes it into shapes the
`Opportunity` schema accepts:

- dates → timezone-aware UTC `datetime`
- modes → one of the `OpportunityMode` literals
- requirement strings → trimmed, deduped, ordered list

Pure functions, no I/O. The spiders import from here so each spider can stay
focused on selectors and not on string-massaging.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import dateparser

# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

# Order matters: try ISO first since it's lossless and unambiguous, fall back
# to dateparser for human strings like "December 10, 2026 11:59 PM UTC".
_DATEPARSER_SETTINGS = {
    "RETURN_AS_TIMEZONE_AWARE": True,
    "TIMEZONE": "UTC",
    "TO_TIMEZONE": "UTC",
    "PREFER_DATES_FROM": "future",
}


def parse_deadline(raw: str) -> datetime:
    """Parse a deadline string into a UTC-aware datetime.

    Tries `datetime.fromisoformat` first (handles `<time datetime="...">`
    attributes from real Devpost pages), then falls back to dateparser for
    free-form strings like "December 10, 2026 11:59 PM UTC".

    Raises `ValueError` if neither path produces a usable datetime — the
    caller (spider) treats this as a hard parse failure and drops the row.
    """
    s = raw.strip()
    if not s:
        raise ValueError("Empty deadline string")

    # Normalize trailing Z to +00:00 — fromisoformat in 3.11+ accepts both,
    # but old fixtures may use Z.
    iso_candidate = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(iso_candidate)
    except ValueError:
        dt = None

    if dt is None:
        dt = dateparser.parse(s, settings=_DATEPARSER_SETTINGS)

    if dt is None:
        raise ValueError(f"Could not parse deadline: {raw!r}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Mode
# ---------------------------------------------------------------------------

_REMOTE_TOKENS = ("remote", "online", "virtual", "anywhere")
_HYBRID_TOKENS = ("hybrid",)


def normalize_mode(raw: str) -> str:
    """Map a free-text location string to one of `Remote`/`In-Person`/`Hybrid`.

    Defaults to `Remote` if the string is empty — most hackathons listed on
    Devpost are remote-friendly, and `Remote` is the safest fallback for the
    deadman switch math (no travel buffer assumed).
    """
    s = (raw or "").strip().lower()
    if not s:
        return "Remote"
    if any(tok in s for tok in _HYBRID_TOKENS):
        return "Hybrid"
    if any(tok in s for tok in _REMOTE_TOKENS):
        return "Remote"
    return "In-Person"


# ---------------------------------------------------------------------------
# Requirements / themes
# ---------------------------------------------------------------------------

# Common scrape noise we never want in raw_requirements
_NOISE_PATTERNS = (
    re.compile(r"^\s*$"),
    re.compile(r"^\d+\s*$"),  # bare numbers from listicle bullets
)


def normalize_requirements(raw: list[str]) -> list[str]:
    """Trim, dedupe (case-insensitive), and order-preserve a tag list.

    Pydantic accepts an empty list — we don't fabricate placeholders here.
    """
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        cleaned = (item or "").strip()
        if not cleaned:
            continue
        if any(p.match(cleaned) for p in _NOISE_PATTERNS):
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


# ---------------------------------------------------------------------------
# Strings
# ---------------------------------------------------------------------------


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace (including newlines) into single spaces."""
    return re.sub(r"\s+", " ", text or "").strip()
