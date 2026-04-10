"""The contract lock.

If this test passes, every component in Astra can trust that the canonical
fixture in `docs/sample_digest.json` validates against the Pydantic models in
`astra_schemas.opportunity`. If it fails, *everything downstream is broken* —
fix it before writing any more code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astra_schemas import Opportunity

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "docs" / "sample_digest.json"


@pytest.fixture(scope="module")
def fixture_text() -> str:
    assert FIXTURE_PATH.exists(), f"Canonical fixture missing at {FIXTURE_PATH}"
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_fixture_parses_into_opportunity(fixture_text: str) -> None:
    """The fixture must validate cleanly into the Opportunity model."""
    opp = Opportunity.model_validate_json(fixture_text)
    assert opp.opportunity_id == "uuid-1234-5678-91011"
    assert opp.metadata.title == "Edge AI Innovation Challenge"
    assert opp.metadata.organization == "NVIDIA"
    assert opp.metadata.type == "Hackathon"
    assert opp.metadata.mode == "Remote"
    assert opp.metadata.raw_requirements == ["Python", "TensorFlow", "Raspberry Pi", "YOLOv8"]


def test_match_analysis_scores_in_range(fixture_text: str) -> None:
    opp = Opportunity.model_validate_json(fixture_text)
    assert 0 <= opp.match_analysis.overall_fit_percentage <= 100
    assert 0 <= opp.match_analysis.semantic_overlap_score <= 100
    assert 0 <= opp.match_analysis.user_trust_score <= 100
    assert opp.match_analysis.ai_reasoning.startswith("Why it fits:")


def test_execution_intel_dates_parse(fixture_text: str) -> None:
    opp = Opportunity.model_validate_json(fixture_text)
    assert opp.execution_intel.complexity_to_time_ratio == "High"
    assert opp.execution_intel.estimated_hours_required == 40
    # recommended start should be before the deadline
    assert opp.execution_intel.recommended_start_date_iso < opp.metadata.deadline_iso


def test_bridge_roadmap_has_resources(fixture_text: str) -> None:
    opp = Opportunity.model_validate_json(fixture_text)
    assert opp.readiness_engine.skill_gap_identified == ["YOLOv8", "TensorRT"]
    assert len(opp.readiness_engine.bridge_roadmap) == 2

    day1 = opp.readiness_engine.bridge_roadmap[0]
    assert day1.day == 1
    assert day1.focus == "YOLOv8 Architecture Basics"
    assert len(day1.resources) == 2
    assert day1.resources[0].type == "Video"
    assert day1.resources[1].type == "Doc"


def test_teammate_matchmaker_present(fixture_text: str) -> None:
    opp = Opportunity.model_validate_json(fixture_text)
    team = opp.teammate_matchmaker.suggested_super_team
    assert len(team) == 2
    assert team[0].name == "Alex Backend"
    assert team[0].compatibility_score == 92


def test_roundtrip_serialization(fixture_text: str) -> None:
    """Validate -> dump -> validate must produce an identical model."""
    original = Opportunity.model_validate_json(fixture_text)
    dumped = original.model_dump_json()
    reparsed = Opportunity.model_validate_json(dumped)
    assert reparsed == original


def test_extra_fields_rejected() -> None:
    """The contract is strict — unknown top-level fields must fail validation."""
    bad_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    bad_payload["totally_made_up_field"] = "boom"
    with pytest.raises(Exception):
        Opportunity.model_validate(bad_payload)
