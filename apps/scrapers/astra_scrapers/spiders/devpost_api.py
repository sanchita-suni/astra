"""Devpost API scraper — fetches real, currently active hackathons.

Devpost exposes a public JSON API at `/api/hackathons` that returns structured
data. This is far more reliable than HTML parsing and gives us clean fields.

Usage:
    from astra_scrapers.spiders.devpost_api import fetch_open_hackathons
    hackathons = fetch_open_hackathons()  # returns list[ScrapedOpportunity]
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import dateparser
import httpx

from astra_scrapers.normalize import normalize_mode, normalize_requirements, parse_deadline
from astra_scrapers.types import ScrapedOpportunity

logger = logging.getLogger("astra.scrapers.devpost_api")

DEVPOST_API_URL = "https://devpost.com/api/hackathons"
SOURCE = "Devpost"

# Map Devpost's broad theme categories to concrete tech skills that the
# analyst can meaningfully match against a user's GitHub profile.
THEME_TO_SKILLS: dict[str, list[str]] = {
    "Machine Learning/AI": ["Python", "TensorFlow", "PyTorch", "Machine Learning"],
    "Web": ["JavaScript", "React", "HTML", "CSS", "Node.js"],
    "Mobile": ["React Native", "Flutter", "Swift", "Kotlin"],
    "IoT": ["Raspberry Pi", "Arduino", "Python", "C++"],
    "Blockchain": ["Solidity", "Web3", "JavaScript", "Rust"],
    "AR/VR": ["Unity", "C#", "Three.js", "WebXR"],
    "Cybersecurity": ["Python", "Linux", "Networking", "Cryptography"],
    "DevOps": ["Docker", "Kubernetes", "CI/CD", "AWS"],
    "Fintech": ["Python", "API", "REST API", "SQL"],
    "Design": ["Figma", "CSS", "UI/UX"],
    "Quantum": ["Python", "Qiskit", "Linear Algebra"],
    "Robotic Process Automation": ["Python", "Automation", "API"],
    "Voice skills": ["Python", "NLP", "API"],
    "Low/No Code": ["API", "Automation"],
}

# Extra tech keywords detected from hackathon titles
TITLE_TECH_KEYWORDS: dict[str, str] = {
    "ai": "Machine Learning", "ml": "Machine Learning",
    "llm": "LLM", "gpt": "LLM", "gemini": "LLM",
    "hack": "", "hackathon": "",  # ignore generic
    "python": "Python", "react": "React", "next": "Next.js",
    "rust": "Rust", "go": "Go", "java": "Java",
    "flutter": "Flutter", "swift": "Swift", "kotlin": "Kotlin",
    "blockchain": "Blockchain", "web3": "Web3",
    "docker": "Docker", "kubernetes": "Kubernetes",
    "data": "Data Science", "analytics": "Data Science",
    "cloud": "Cloud", "aws": "AWS", "azure": "Azure", "gcp": "GCP",
    "iot": "IoT", "arduino": "Arduino",
    "design": "UI/UX", "figma": "Figma",
    "mobile": "Mobile", "ios": "iOS", "android": "Android",
    "security": "Cybersecurity", "cyber": "Cybersecurity",
}


def _extract_skills_from_themes_and_title(
    themes: list[dict], title: str
) -> list[str]:
    """Convert broad Devpost themes + title keywords into concrete tech skills."""
    skills: list[str] = []
    seen: set[str] = set()

    # Map themes to real skills
    for theme in themes:
        name = theme.get("name", "") if isinstance(theme, dict) else str(theme)
        mapped = THEME_TO_SKILLS.get(name, [])
        for skill in mapped:
            if skill.lower() not in seen:
                skills.append(skill)
                seen.add(skill.lower())

    # Extract tech from title
    title_lower = title.lower()
    for keyword, skill in TITLE_TECH_KEYWORDS.items():
        if skill and keyword in title_lower and skill.lower() not in seen:
            skills.append(skill)
            seen.add(skill.lower())

    return skills


def _parse_submission_dates(date_str: str) -> datetime | None:
    """Parse Devpost date ranges like 'Mar 28 - Apr 10, 2026'.

    We want the deadline (end date), which is the part after the dash.
    """
    if not date_str:
        return None
    # Split on dash and take the last part
    parts = date_str.split("-")
    end_part = parts[-1].strip()
    # If the end part doesn't include a year, try to infer it
    try:
        return parse_deadline(end_part)
    except ValueError:
        # Try with the full string
        try:
            return parse_deadline(date_str)
        except ValueError:
            return None


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def _parse_hackathon(h: dict) -> ScrapedOpportunity | None:
    """Convert a single Devpost API hackathon object to a ScrapedOpportunity."""
    title = (h.get("title") or "").strip()
    if not title:
        return None

    url = h.get("url") or h.get("start_a_submission_url") or ""
    if not url:
        return None

    organization = (h.get("organization_name") or "Unknown").strip()

    # Parse deadline from submission_period_dates
    date_str = h.get("submission_period_dates") or ""
    deadline = _parse_submission_dates(date_str)
    if deadline is None:
        # Default to 30 days from now if we can't parse
        deadline = datetime.now(timezone.utc).replace(
            hour=23, minute=59, second=0
        )
        from datetime import timedelta
        deadline += timedelta(days=30)

    # Map themes + title to real tech skills
    themes = h.get("themes") or []
    raw_requirements = normalize_requirements(
        _extract_skills_from_themes_and_title(themes, title)
    )

    # Mode from location
    location = h.get("displayed_location") or ""
    mode = normalize_mode(location.get("location", "") if isinstance(location, dict) else str(location))

    opportunity_id = f"devpost-{_slugify(title)}"

    try:
        return ScrapedOpportunity(
            opportunity_id=opportunity_id,
            title=title,
            organization=organization,
            source=SOURCE,
            type="Hackathon",
            mode=mode,
            deadline=deadline,
            apply_link=url,
            raw_requirements=raw_requirements,
        )
    except Exception as exc:
        logger.warning("Failed to parse hackathon %r: %s", title, exc)
        return None


def fetch_open_hackathons(
    *,
    max_pages: int = 5,
    status: str = "open",
    order_by: str = "deadline",
) -> list[ScrapedOpportunity]:
    """Fetch currently open hackathons from Devpost's public API.

    Returns validated `ScrapedOpportunity` objects ready for
    `to_stub_opportunity()` → analyst enrichment → DB upsert.
    """
    all_hackathons: list[ScrapedOpportunity] = []
    page = 1

    while page <= max_pages:
        try:
            resp = httpx.get(
                DEVPOST_API_URL,
                params={"status": status, "order_by": order_by, "page": page},
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Devpost API request failed (page %d): %s", page, exc)
            break

        data = resp.json()
        hackathons = data.get("hackathons", [])
        if not hackathons:
            break

        for h in hackathons:
            parsed = _parse_hackathon(h)
            if parsed is not None:
                all_hackathons.append(parsed)

        # Check if there are more pages
        meta = data.get("meta", {})
        total_count = meta.get("total_count", 0)
        per_page = meta.get("per_page", len(hackathons))
        if page * per_page >= total_count:
            break
        page += 1

    logger.info("Fetched %d hackathons from Devpost API", len(all_hackathons))
    return all_hackathons
