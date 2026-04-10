"""MLH (Major League Hacking) scraper.

MLH publishes their season events as a JSON-LD feed on mlh.io. We can also
hit their events page which returns structured data.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import httpx

from astra_scrapers.normalize import normalize_mode, normalize_requirements, parse_deadline
from astra_scrapers.types import ScrapedOpportunity

logger = logging.getLogger("astra.scrapers.mlh")

MLH_EVENTS_URL = "https://mlh.io/seasons/2026/events"
SOURCE = "MLH"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def _parse_event(event: dict) -> ScrapedOpportunity | None:
    """Parse an MLH event from JSON-LD or scraped data."""
    name = (event.get("name") or "").strip()
    if not name:
        return None

    url = event.get("url") or event.get("website") or ""
    if not url:
        return None

    # Parse dates
    end_date_str = event.get("endDate") or event.get("end_date") or ""
    deadline: datetime | None = None
    if end_date_str:
        try:
            deadline = parse_deadline(str(end_date_str))
        except ValueError:
            pass
    if deadline is None:
        from datetime import timedelta
        deadline = datetime.now(timezone.utc) + timedelta(days=14)

    # Location / mode
    location = event.get("location") or ""
    if isinstance(location, dict):
        location = location.get("name", "") or location.get("address", {}).get("addressLocality", "")
    mode = normalize_mode(str(location))

    # MLH hackathons are general-purpose
    raw_requirements: list[str] = []
    themes = event.get("themes") or event.get("tags") or []
    if isinstance(themes, list):
        raw_requirements = normalize_requirements(
            [t if isinstance(t, str) else t.get("name", "") for t in themes]
        )

    try:
        return ScrapedOpportunity(
            opportunity_id=f"mlh-{_slugify(name)}",
            title=name,
            organization="Major League Hacking",
            source=SOURCE,
            type="Hackathon",
            mode=mode,
            deadline=deadline,
            apply_link=url,
            raw_requirements=raw_requirements,
        )
    except Exception as exc:
        logger.warning("MLH parse failed for %r: %s", name, exc)
        return None


def fetch_mlh_events() -> list[ScrapedOpportunity]:
    """Fetch MLH season events by scraping the events page for JSON-LD."""
    import json
    from bs4 import BeautifulSoup

    try:
        resp = httpx.get(
            MLH_EVENTS_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            },
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("MLH fetch failed: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    events: list[ScrapedOpportunity] = []

    # Try JSON-LD first
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                for item in data:
                    parsed = _parse_event(item)
                    if parsed:
                        events.append(parsed)
            elif isinstance(data, dict):
                if data.get("@type") == "Event":
                    parsed = _parse_event(data)
                    if parsed:
                        events.append(parsed)
        except json.JSONDecodeError:
            continue

    # Fallback: parse event cards from HTML
    if not events:
        for card in soup.select(".event-wrapper, .event, [class*='event']"):
            name_el = card.select_one("h3, h4, .event-name, [class*='name']")
            link_el = card.select_one("a[href]")
            date_el = card.select_one("[class*='date'], time")

            if not name_el or not link_el:
                continue

            name = name_el.get_text(strip=True)
            href = link_el.get("href", "")
            if isinstance(href, list):
                href = href[0] if href else ""
            if href and not href.startswith("http"):
                href = f"https://mlh.io{href}"

            date_str = ""
            if date_el:
                date_str = date_el.get("datetime", "") or date_el.get_text(strip=True)

            event_data = {"name": name, "url": href, "endDate": date_str}
            parsed = _parse_event(event_data)
            if parsed:
                events.append(parsed)

    logger.info("Fetched %d events from MLH", len(events))
    return events
