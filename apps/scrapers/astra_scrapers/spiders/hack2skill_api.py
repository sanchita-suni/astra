"""Hack2Skill scraper — HTML parsing since they don't expose a public API."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup

from astra_scrapers.normalize import normalize_mode, normalize_requirements, parse_deadline
from astra_scrapers.types import ScrapedOpportunity

logger = logging.getLogger("astra.scrapers.hack2skill")

HACK2SKILL_URL = "https://hack2skill.com/hackathons"
SOURCE = "Hack2Skill"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def fetch_hack2skill() -> list[ScrapedOpportunity]:
    """Scrape hackathons from Hack2Skill's listing page."""
    try:
        resp = httpx.get(
            HACK2SKILL_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            },
            timeout=15,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Hack2Skill fetch failed: %s", exc)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results: list[ScrapedOpportunity] = []

    # Look for hackathon cards — Hack2Skill uses various card-like structures
    cards = soup.select(
        ".hackathon-card, .card, [class*='hackathon'], [class*='challenge']"
    )

    for card in cards:
        try:
            # Find title
            title_el = card.select_one("h3, h4, h5, .title, [class*='title'], a[class*='name']")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            # Find link
            link_el = card.select_one("a[href]")
            href = ""
            if link_el:
                href = link_el.get("href", "")
                if isinstance(href, list):
                    href = href[0] if href else ""
                if href and not href.startswith("http"):
                    href = f"https://hack2skill.com{href}"
            if not href:
                continue

            # Find date
            date_el = card.select_one("time, [class*='date'], [class*='deadline']")
            deadline = datetime.now(timezone.utc) + timedelta(days=30)
            if date_el:
                date_text = date_el.get("datetime", "") or date_el.get_text(strip=True)
                try:
                    deadline = parse_deadline(date_text)
                except ValueError:
                    pass

            results.append(
                ScrapedOpportunity(
                    opportunity_id=f"hack2skill-{_slugify(title)}",
                    title=title,
                    organization="Hack2Skill",
                    source=SOURCE,
                    type="Hackathon",
                    mode="Remote",
                    deadline=deadline,
                    apply_link=href,
                    raw_requirements=[],
                )
            )
        except Exception as exc:
            logger.debug("Hack2Skill card parse error: %s", exc)
            continue

    logger.info("Fetched %d from Hack2Skill", len(results))
    return results
