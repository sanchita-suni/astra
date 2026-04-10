"""Unstop (formerly D2C) scraper — fetches hackathons and competitions.

Unstop has a public API at unstop.com/api that returns JSON. We hit the
competitions/hackathon listings endpoint.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from astra_scrapers.normalize import normalize_mode, normalize_requirements, parse_deadline
from astra_scrapers.types import ScrapedOpportunity

logger = logging.getLogger("astra.scrapers.unstop_api")

UNSTOP_API_URL = "https://unstop.com/api/public/opportunity/search-new"
SOURCE = "Unstop"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def _parse_item(item: dict) -> ScrapedOpportunity | None:
    """Parse a single Unstop API item."""
    title = (item.get("title") or "").strip()
    if not title:
        return None

    # Build the URL
    slug = item.get("public_url") or item.get("seo_url") or ""
    if slug:
        url = f"https://unstop.com/hackathons/{slug}" if not slug.startswith("http") else slug
    else:
        opp_id = item.get("id", "")
        url = f"https://unstop.com/competition/{opp_id}"

    organization = (item.get("organisation", {}).get("name", "") if isinstance(item.get("organisation"), dict) else "") or "Unknown"

    # Deadline
    end_date = item.get("end_date") or item.get("regnEnd") or ""
    deadline: datetime | None = None
    if end_date:
        try:
            deadline = parse_deadline(str(end_date))
        except ValueError:
            pass
    if deadline is None:
        from datetime import timedelta
        deadline = datetime.now(timezone.utc) + timedelta(days=30)

    # Type
    opp_type = "Hackathon"
    category = (item.get("type") or item.get("opportunity_type") or "").lower()
    if "intern" in category:
        opp_type = "Internship"

    # Requirements / tags
    tags = []
    for skill in (item.get("filters", {}).get("skills", []) if isinstance(item.get("filters"), dict) else []):
        if isinstance(skill, dict):
            tags.append(skill.get("name", ""))
        elif isinstance(skill, str):
            tags.append(skill)
    raw_requirements = normalize_requirements(tags)

    mode = normalize_mode(item.get("festival_type", "") or "")

    try:
        return ScrapedOpportunity(
            opportunity_id=f"unstop-{_slugify(title)}",
            title=title,
            organization=organization,
            source=SOURCE,
            type=opp_type,
            mode=mode,
            deadline=deadline,
            apply_link=url,
            raw_requirements=raw_requirements,
        )
    except Exception as exc:
        logger.warning("Failed to parse Unstop item %r: %s", title, exc)
        return None


def fetch_unstop_opportunities(
    *,
    max_pages: int = 3,
    opportunity_type: str = "hackathon",
) -> list[ScrapedOpportunity]:
    """Fetch opportunities from Unstop's public API."""
    all_opps: list[ScrapedOpportunity] = []
    page = 1

    while page <= max_pages:
        try:
            resp = httpx.post(
                UNSTOP_API_URL,
                json={
                    "opportunity": opportunity_type,
                    "per_page": 15,
                    "page": page,
                    "oppstatus": "open",
                },
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Unstop API failed (page %d): %s", page, exc)
            break

        data = resp.json()
        items = data.get("data", {}).get("data", []) if isinstance(data.get("data"), dict) else []
        if not items:
            break

        for item in items:
            parsed = _parse_item(item)
            if parsed is not None:
                all_opps.append(parsed)

        page += 1

    logger.info("Fetched %d opportunities from Unstop", len(all_opps))
    return all_opps
