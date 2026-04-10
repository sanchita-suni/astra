"""HackerEarth scraper — public API for hackathons and hiring challenges."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from astra_scrapers.normalize import normalize_mode, normalize_requirements, parse_deadline
from astra_scrapers.types import ScrapedOpportunity

logger = logging.getLogger("astra.scrapers.hackerearth")

HACKEREARTH_API = "https://www.hackerearth.com/api/events/upcoming/"
SOURCE = "HackerEarth"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def _parse_event(ev: dict) -> ScrapedOpportunity | None:
    title = (ev.get("title") or "").strip()
    if not title:
        return None

    url = ev.get("url") or ev.get("subscribe") or ""
    if not url:
        return None

    # Parse end date
    end_str = ev.get("end_date") or ""
    deadline: datetime | None = None
    if end_str:
        try:
            deadline = parse_deadline(str(end_str))
        except ValueError:
            pass
    if deadline is None:
        from datetime import timedelta
        deadline = datetime.now(timezone.utc) + timedelta(days=14)

    # Determine type
    challenge_type = (ev.get("challenge_type") or "").lower()
    opp_type = "Hackathon"
    if "hiring" in title.lower() or "hiring" in challenge_type:
        opp_type = "Internship"

    # Extract tech from title/description
    desc = (ev.get("description") or "")[:500]
    text = f"{title} {desc}".lower()
    skills: list[str] = []
    tech_map = {
        "python": "Python", "java": "Java", "javascript": "JavaScript",
        "react": "React", "node": "Node.js", "machine learning": "Machine Learning",
        "ai": "AI", "data science": "Data Science", "sql": "SQL",
        "c++": "C++", "golang": "Go", "rust": "Rust", "docker": "Docker",
    }
    for kw, skill in tech_map.items():
        if kw in text:
            skills.append(skill)

    try:
        return ScrapedOpportunity(
            opportunity_id=f"hackerearth-{_slugify(title)}",
            title=title,
            organization="HackerEarth",
            source=SOURCE,
            type=opp_type,
            mode="Remote",
            deadline=deadline,
            apply_link=url,
            raw_requirements=normalize_requirements(skills),
        )
    except Exception as exc:
        logger.warning("HackerEarth parse failed: %s", exc)
        return None


def fetch_hackerearth_events() -> list[ScrapedOpportunity]:
    """Fetch upcoming hackathons and challenges from HackerEarth."""
    results: list[ScrapedOpportunity] = []

    for event_type in ["hackathon", "hiring"]:
        try:
            resp = httpx.get(
                HACKEREARTH_API,
                params={"type": event_type},
                headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            events = data.get("response", [])
            for ev in events:
                parsed = _parse_event(ev)
                if parsed:
                    results.append(parsed)
        except httpx.HTTPError as exc:
            logger.warning("HackerEarth fetch failed for %s: %s", event_type, exc)

    logger.info("Fetched %d events from HackerEarth", len(results))
    return results
