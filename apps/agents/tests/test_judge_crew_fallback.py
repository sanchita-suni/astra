"""judge_crew fallback tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from astra_agents.crews.judge_crew import run_dry_run
from astra_schemas import (
    DryRunRubric,
    ExecutionIntel,
    JudgeScore,
    MatchAnalysis,
    Metadata,
    Opportunity,
    ReadinessEngine,
    RubricBreakdown,
    TeammateMatchmaker,
)

DEADLINE = datetime(2026, 12, 10, tzinfo=timezone.utc)


def _opp() -> Opportunity:
    return Opportunity(
        opportunity_id="test-rehearsal",
        metadata=Metadata(
            title="Edge AI Innovation Challenge",
            organization="NVIDIA",
            source="Devpost",
            type="Hackathon",
            mode="Remote",
            deadline_iso=DEADLINE,
            apply_link="https://devpost.com/software/test",  # type: ignore[arg-type]
            raw_requirements=["Python", "TensorFlow", "Raspberry Pi", "YOLOv8"],
        ),
        match_analysis=MatchAnalysis(
            overall_fit_percentage=70,
            semantic_overlap_score=80,
            user_trust_score=60,
            ai_reasoning="Why it fits: overlap.",
        ),
        execution_intel=ExecutionIntel(
            complexity_to_time_ratio="Medium",
            estimated_hours_required=32,
            recommended_start_date_iso=DEADLINE - timedelta(days=14),
            deadman_switch_alert="Start by Nov 28.",
        ),
        readiness_engine=ReadinessEngine(skill_gap_identified=[], bridge_roadmap=[]),
        teammate_matchmaker=TeammateMatchmaker(suggested_super_team=[]),
    )


GOOD_PITCH = (
    "We're building a real-time pothole detector that runs on a Raspberry Pi "
    "with a camera module. The user is any city public-works department that "
    "wants to automate road-condition surveys. We use YOLOv8 for detection and "
    "deploy an MVP API endpoint so field crews can snap a photo and get a "
    "severity score back in under 2 seconds."
)

SHORT_PITCH = "We are making a novel app."


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def test_dry_run_returns_three_judges() -> None:
    opp = _opp()
    result = run_dry_run(opp, GOOD_PITCH, use_llm=False)
    assert isinstance(result, DryRunRubric)
    assert len(result.scores) == 3
    judges = {s.judge for s in result.scores}
    assert judges == {"industry", "academic", "vc"}
    assert result.rubric_source == "fallback"


def test_dry_run_scores_in_range() -> None:
    result = run_dry_run(_opp(), GOOD_PITCH, use_llm=False)
    for s in result.scores:
        assert 0 <= s.score <= 100
        assert 0 <= s.rubric.feasibility <= 25
        assert 0 <= s.rubric.novelty <= 25
        assert 0 <= s.rubric.market_fit <= 25
        assert 0 <= s.rubric.polish <= 25
        # Sum matches
        total = s.rubric.feasibility + s.rubric.novelty + s.rubric.market_fit + s.rubric.polish
        assert s.score == total


def test_dry_run_overall_is_average_of_scores() -> None:
    result = run_dry_run(_opp(), GOOD_PITCH, use_llm=False)
    avg = round(sum(s.score for s in result.scores) / len(result.scores))
    assert result.overall_score == avg


def test_repo_url_bumps_feasibility_and_polish() -> None:
    opp = _opp()
    without = run_dry_run(opp, GOOD_PITCH, repo_url=None, use_llm=False)
    with_repo = run_dry_run(opp, GOOD_PITCH, repo_url="https://github.com/a/b", use_llm=False)
    assert with_repo.overall_score >= without.overall_score


def test_good_pitch_scores_higher_than_short_pitch() -> None:
    opp = _opp()
    good = run_dry_run(opp, GOOD_PITCH, use_llm=False)
    short = run_dry_run(opp, SHORT_PITCH, use_llm=False)
    assert good.overall_score > short.overall_score


def test_feedback_strings_nonempty() -> None:
    result = run_dry_run(_opp(), GOOD_PITCH, use_llm=False)
    for s in result.scores:
        assert len(s.feedback) > 10
    assert len(result.overall_feedback) > 10


def test_persona_bias_visible_in_scores() -> None:
    """Each persona should have their biased dimension >= other personas'."""
    result = run_dry_run(_opp(), GOOD_PITCH, use_llm=False)
    by_judge = {s.judge: s for s in result.scores}
    # Industry biases feasibility
    assert by_judge["industry"].rubric.feasibility >= by_judge["academic"].rubric.feasibility
    # Academic biases novelty
    assert by_judge["academic"].rubric.novelty >= by_judge["industry"].rubric.novelty
    # VC biases market fit
    assert by_judge["vc"].rubric.market_fit >= by_judge["industry"].rubric.market_fit
