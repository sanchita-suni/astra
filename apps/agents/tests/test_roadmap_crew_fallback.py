"""roadmap_crew fallback tests."""

from __future__ import annotations

from astra_agents.crews.roadmap_crew import (
    attach_roadmap_to_opportunity,
    generate_bridge_roadmap,
)
from astra_schemas import BridgeRoadmapDay


def test_empty_skill_gap_returns_empty_roadmap() -> None:
    assert generate_bridge_roadmap([], use_llm=False) == []


def test_curated_resources_used_for_known_skill() -> None:
    days = generate_bridge_roadmap(["TensorFlow"], days=2, use_llm=False)
    assert len(days) == 2
    for day in days:
        assert isinstance(day, BridgeRoadmapDay)
        assert len(day.resources) >= 1
        # All TensorFlow resources should be tensorflow.org links
        urls = [str(r.url) for r in day.resources]
        assert any("tensorflow.org" in u or "youtube.com" in u for u in urls)


def test_unknown_skill_falls_back_to_search_links() -> None:
    days = generate_bridge_roadmap(["Brand-New-Skill-2026"], days=3, use_llm=False)
    assert len(days) == 3
    urls = [str(r.url) for d in days for r in d.resources]
    assert any("github.com/search" in u for u in urls)


def test_roadmap_round_robins_multiple_skills() -> None:
    days = generate_bridge_roadmap(["Python", "TensorFlow", "YOLOv8"], days=6, use_llm=False)
    focuses = [d.focus for d in days]
    assert any("Python" in f for f in focuses)
    assert any("TensorFlow" in f for f in focuses)
    assert any("YOLOv8" in f for f in focuses)


def test_roadmap_day_numbers_are_sequential_and_in_range() -> None:
    days = generate_bridge_roadmap(["Python"], days=7, use_llm=False)
    assert [d.day for d in days] == [1, 2, 3, 4, 5, 6, 7]


def test_first_and_last_day_focus_differ_from_middle() -> None:
    """Day 1 should be 'set up'; last day should be 'integrate'."""
    days = generate_bridge_roadmap(["Python"], days=7, use_llm=False)
    assert "set up" in days[0].focus.lower()
    assert "integrate" in days[-1].focus.lower()


def test_attach_roadmap_to_opportunity_populates_bridge() -> None:
    from datetime import datetime, timedelta, timezone

    from astra_schemas import (
        ExecutionIntel,
        MatchAnalysis,
        Metadata,
        Opportunity,
        ReadinessEngine,
        TeammateMatchmaker,
    )

    deadline = datetime(2026, 12, 10, tzinfo=timezone.utc)
    opp = Opportunity(
        opportunity_id="x",
        metadata=Metadata(
            title="Test",
            organization="Acme",
            source="Devpost",
            type="Hackathon",
            mode="Remote",
            deadline_iso=deadline,
            apply_link="https://example.com/apply",  # type: ignore[arg-type]
            raw_requirements=["Python"],
        ),
        match_analysis=MatchAnalysis(
            overall_fit_percentage=50,
            semantic_overlap_score=50,
            user_trust_score=50,
            ai_reasoning="Why it fits: test.",
        ),
        execution_intel=ExecutionIntel(
            complexity_to_time_ratio="Low",
            estimated_hours_required=8,
            recommended_start_date_iso=deadline - timedelta(days=14),
            deadman_switch_alert="ok",
        ),
        readiness_engine=ReadinessEngine(
            skill_gap_identified=["Python"],
            bridge_roadmap=[],
        ),
        teammate_matchmaker=TeammateMatchmaker(suggested_super_team=[]),
    )

    enriched = attach_roadmap_to_opportunity(opp, use_llm=False)
    assert len(enriched.readiness_engine.bridge_roadmap) == 7
    # Skill gap is preserved
    assert enriched.readiness_engine.skill_gap_identified == ["Python"]
    # Other sections untouched
    assert enriched.metadata == opp.metadata
    assert enriched.match_analysis == opp.match_analysis
