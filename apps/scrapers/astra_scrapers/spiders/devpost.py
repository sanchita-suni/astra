"""Devpost hackathon parser.

Pure parsing — takes HTML in, returns a `ScrapedOpportunity`. The Day 2
contract is the fixture at `apps/scrapers/fixtures/devpost_*.html`; once
selectors are stable against the fixture, the same function will be wired into
a Scrapy spider that fetches live Devpost pages from inside the compose
container (Scrapy + Playwright on the Windows host is the #1 risk in the
plan, so we run it server-side only).

Selector contract is documented inside the fixture HTML — keep them in sync.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from astra_scrapers.normalize import (
    collapse_whitespace,
    normalize_mode,
    normalize_requirements,
    parse_deadline,
)
from astra_scrapers.types import ScrapedOpportunity

SOURCE = "Devpost"


def parse_devpost_html(html: str) -> ScrapedOpportunity:
    """Parse a saved Devpost hackathon detail page into a `ScrapedOpportunity`.

    Raises `ValueError` if any required field is missing — better to drop a
    bad row than to silently emit a malformed Opportunity.
    """
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("h1.hackathon-name")
    org_el = soup.select_one(".organization-name")
    deadline_el = soup.select_one(".submission-period time")
    apply_el = soup.select_one("a.apply-link")
    mode_el = soup.select_one(".location-mode")
    id_el = soup.select_one(".opportunity-id")
    theme_els = soup.select("ul.themes li")

    if title_el is None or not title_el.get_text(strip=True):
        raise ValueError("Devpost parse: missing h1.hackathon-name")
    if org_el is None or not org_el.get_text(strip=True):
        raise ValueError("Devpost parse: missing .organization-name")
    if deadline_el is None:
        raise ValueError("Devpost parse: missing .submission-period time")
    if apply_el is None or not apply_el.get("href"):
        raise ValueError("Devpost parse: missing a.apply-link href")

    # Prefer the machine-readable datetime attribute; fall back to text.
    deadline_raw = deadline_el.get("datetime") or deadline_el.get_text(strip=True)
    if isinstance(deadline_raw, list):  # bs4 multi-valued attr safety
        deadline_raw = " ".join(deadline_raw)
    deadline = parse_deadline(deadline_raw)

    # Stable, deterministic ID. If the page exposes one, prefer that;
    # otherwise derive from the apply URL slug.
    raw_id: str | None = None
    if id_el is not None:
        raw_id = id_el.get("data-id") or id_el.get_text(strip=True)
    if not raw_id:
        href = apply_el.get("href", "")
        if isinstance(href, list):
            href = href[0] if href else ""
        slug = href.rstrip("/").rsplit("/", 1)[-1] or "unknown"
        raw_id = f"devpost-{slug}"

    title = collapse_whitespace(title_el.get_text())
    organization = collapse_whitespace(org_el.get_text())
    mode_text = collapse_whitespace(mode_el.get_text()) if mode_el is not None else ""
    requirements = normalize_requirements(
        [collapse_whitespace(li.get_text()) for li in theme_els]
    )

    href_val = apply_el.get("href", "")
    if isinstance(href_val, list):
        href_val = href_val[0] if href_val else ""

    return ScrapedOpportunity(
        opportunity_id=raw_id,
        title=title,
        organization=organization,
        source=SOURCE,
        type="Hackathon",
        mode=normalize_mode(mode_text),
        deadline=deadline,
        apply_link=href_val,  # type: ignore[arg-type]  # Pydantic coerces str → HttpUrl
        raw_requirements=requirements,
    )


def parse_devpost_file(path: str | Path) -> ScrapedOpportunity:
    """Convenience for tests / CLI: load a fixture file and parse it."""
    p = Path(path)
    return parse_devpost_html(p.read_text(encoding="utf-8"))
