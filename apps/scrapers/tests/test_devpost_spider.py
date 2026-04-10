"""Devpost parser tests — fixture HTML must round-trip into a valid Opportunity.

If this test passes, the Day 2 ingestion pipeline can take real Devpost-shaped
HTML and produce a row that the FastAPI surface and the Next.js page already
know how to render. That's the whole point of locking the contract on Day 1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from astra_schemas import Opportunity
from astra_scrapers.normalize import (
    normalize_mode,
    normalize_requirements,
    parse_deadline,
)
from astra_scrapers.spiders.devpost import parse_devpost_file, parse_devpost_html
from astra_scrapers.types import ScrapedOpportunity

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "apps" / "scrapers" / "fixtures" / "devpost_edge_ai_challenge.html"


# ---------------------------------------------------------------------------
# Parser end-to-end
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def scraped() -> ScrapedOpportunity:
    assert FIXTURE.exists(), f"fixture missing at {FIXTURE}"
    return parse_devpost_file(FIXTURE)


def test_parses_required_metadata(scraped: ScrapedOpportunity) -> None:
    assert scraped.title == "Edge AI Innovation Challenge"
    assert scraped.organization == "NVIDIA"
    assert scraped.source == "Devpost"
    assert scraped.type == "Hackathon"
    assert scraped.mode == "Remote"
    assert str(scraped.apply_link).startswith(
        "https://devpost.com/software/edge-ai-innovation-challenge"
    )


def test_deadline_is_utc_and_correct(scraped: ScrapedOpportunity) -> None:
    expected = datetime(2026, 12, 10, 23, 59, 0, tzinfo=timezone.utc)
    assert scraped.deadline == expected
    assert scraped.deadline.tzinfo is not None


def test_opportunity_id_is_stable(scraped: ScrapedOpportunity) -> None:
    # Comes from the explicit data-id attribute, not the URL slug
    assert scraped.opportunity_id == "devpost-edge-ai-innovation-challenge"


def test_requirements_extracted_in_order(scraped: ScrapedOpportunity) -> None:
    assert scraped.raw_requirements == ["Python", "TensorFlow", "Raspberry Pi", "YOLOv8"]


def test_scraped_lifts_to_full_opportunity(scraped: ScrapedOpportunity) -> None:
    """The stub bridge must produce a fully-valid Opportunity for the API."""
    opp = scraped.to_stub_opportunity()
    assert isinstance(opp, Opportunity)
    assert opp.opportunity_id == scraped.opportunity_id
    assert opp.metadata.title == scraped.title
    # Placeholder analyst fields are valid but explicitly marked as pending
    assert opp.match_analysis.overall_fit_percentage == 0
    assert opp.match_analysis.ai_reasoning == "(pending analyst crew)"
    assert opp.execution_intel.deadman_switch_alert == "(pending deadman switch)"
    assert opp.readiness_engine.bridge_roadmap == []
    assert opp.teammate_matchmaker.suggested_super_team == []
    # Recommended start defaults to deadline - 7 days
    assert (opp.metadata.deadline_iso - opp.execution_intel.recommended_start_date_iso).days == 7


# ---------------------------------------------------------------------------
# Failure modes — bad HTML must raise, not silently produce garbage
# ---------------------------------------------------------------------------


def test_missing_title_raises() -> None:
    bad = "<html><body><p class='organization-name'>Acme</p></body></html>"
    with pytest.raises(ValueError, match="hackathon-name"):
        parse_devpost_html(bad)


def test_missing_deadline_raises() -> None:
    bad = (
        "<html><body>"
        "<h1 class='hackathon-name'>X</h1>"
        "<p class='organization-name'>Acme</p>"
        "<a class='apply-link' href='https://example.com/x'>apply</a>"
        "</body></html>"
    )
    with pytest.raises(ValueError, match="submission-period"):
        parse_devpost_html(bad)


# ---------------------------------------------------------------------------
# Normalizers — small focused tests so failures point at the right module
# ---------------------------------------------------------------------------


def test_parse_deadline_iso_z_suffix() -> None:
    dt = parse_deadline("2026-12-10T23:59:00Z")
    assert dt == datetime(2026, 12, 10, 23, 59, 0, tzinfo=timezone.utc)


def test_parse_deadline_human_string() -> None:
    dt = parse_deadline("December 10, 2026 11:59 PM UTC")
    assert dt.year == 2026 and dt.month == 12 and dt.day == 10
    assert dt.tzinfo is not None


def test_parse_deadline_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_deadline("")


def test_normalize_mode_variants() -> None:
    assert normalize_mode("Online (Remote)") == "Remote"
    assert normalize_mode("Hybrid - SF + Online") == "Hybrid"
    assert normalize_mode("San Francisco, CA") == "In-Person"
    assert normalize_mode("") == "Remote"


def test_normalize_requirements_dedupes_and_trims() -> None:
    out = normalize_requirements(["  Python ", "python", "TensorFlow", "", "  ", "TensorFlow"])
    assert out == ["Python", "TensorFlow"]
