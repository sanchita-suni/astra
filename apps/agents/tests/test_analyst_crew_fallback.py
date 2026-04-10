"""analyst_crew fallback tests.

These exercise the deterministic path with no LLM. The shape and the math
are the contract; the LLM-written `ai_reasoning` is upgrade-only polish.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from astra_agents.crews.analyst_crew import enrich_opportunity
from astra_core import ProofOfWork
from astra_github_client import RepoSummary, UserSummary
from astra_schemas import (
    ExecutionIntel,
    MatchAnalysis,
    Metadata,
    Opportunity,
    ReadinessEngine,
    TeammateMatchmaker,
)

NOW = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)


def _stub_opp(requirements: list[str]) -> Opportunity:
    """Build a stub Opportunity matching what the scraper bridge produces."""
    deadline = NOW + timedelta(days=30)
    return Opportunity(
        opportunity_id="test-opp",
        metadata=Metadata(
            title="Edge AI Innovation Challenge",
            organization="NVIDIA",
            source="Devpost",
            type="Hackathon",
            mode="Remote",
            deadline_iso=deadline,
            apply_link="https://devpost.com/software/test",  # type: ignore[arg-type]
            raw_requirements=requirements,
        ),
        match_analysis=MatchAnalysis(
            overall_fit_percentage=0,
            semantic_overlap_score=0,
            user_trust_score=0,
            ai_reasoning="(pending analyst crew)",
        ),
        execution_intel=ExecutionIntel(
            complexity_to_time_ratio="Medium",
            estimated_hours_required=20,
            recommended_start_date_iso=deadline - timedelta(days=7),
            deadman_switch_alert="(pending deadman switch)",
        ),
        readiness_engine=ReadinessEngine(skill_gap_identified=[], bridge_roadmap=[]),
        teammate_matchmaker=TeammateMatchmaker(suggested_super_team=[]),
    )


def _user(*, langs: list[str], topics: list[str], stars: int = 10, days_since_push: int = 4) -> ProofOfWork:
    repos = [
        RepoSummary(
            full_name=f"alice/repo-{i}",
            name=f"repo-{i}",
            language=langs[i % max(1, len(langs))] if langs else None,
            stargazers_count=stars // max(1, len(langs)),
            html_url=f"https://github.com/alice/repo-{i}",
            topics=topics if i == 0 else [],
        )
        for i in range(max(1, len(langs)))
    ]
    return ProofOfWork(
        user=UserSummary(
            login="alice",
            name="Alice",
            bio="ML engineer who ships",
            public_repos=len(repos),
            followers=20,
            html_url="https://github.com/alice",
        ),
        repos=repos,
        languages_top=[(lang, 1) for lang in langs],
        total_stars=stars,
        days_since_last_push=days_since_push,
    )


# ---------------------------------------------------------------------------
# Core enrichment
# ---------------------------------------------------------------------------


def test_enrich_opportunity_full_overlap_max_score() -> None:
    """All requirements covered → 100% overlap, no skill gap."""
    stub = _stub_opp(["Python", "TensorFlow"])
    user = _user(langs=["Python", "TensorFlow"], topics=[], stars=50)
    enriched = enrich_opportunity(stub, user, use_llm=False, now=NOW)

    assert isinstance(enriched, Opportunity)
    assert enriched.match_analysis.semantic_overlap_score == 100
    assert enriched.readiness_engine.skill_gap_identified == []
    assert enriched.match_analysis.ai_reasoning.startswith("Why it fits:")
    assert enriched.match_analysis.ai_reasoning != "(pending analyst crew)"


def test_enrich_opportunity_partial_overlap_identifies_gap() -> None:
    """Half coverage → 50% overlap, the missing skill is in the gap list."""
    stub = _stub_opp(["Python", "TensorFlow"])
    user = _user(langs=["Python"], topics=[], stars=10)
    enriched = enrich_opportunity(stub, user, use_llm=False, now=NOW)

    assert enriched.match_analysis.semantic_overlap_score == 50
    assert enriched.readiness_engine.skill_gap_identified == ["TensorFlow"]


def test_enrich_opportunity_no_overlap_zero_score() -> None:
    stub = _stub_opp(["Rust", "WebAssembly"])
    user = _user(langs=["Python"], topics=[], stars=5)
    enriched = enrich_opportunity(stub, user, use_llm=False, now=NOW)

    assert enriched.match_analysis.semantic_overlap_score == 0
    assert enriched.readiness_engine.skill_gap_identified == ["Rust", "WebAssembly"]


def test_enrich_opportunity_topics_count_as_signal() -> None:
    """Repo topics should also count as user signal, not just language."""
    stub = _stub_opp(["raspberry-pi", "TensorFlow"])
    user = _user(langs=["Python"], topics=["raspberry-pi", "tensorflow"], stars=10)
    enriched = enrich_opportunity(stub, user, use_llm=False, now=NOW)
    assert enriched.match_analysis.semantic_overlap_score == 100
    assert enriched.readiness_engine.skill_gap_identified == []


def test_enrich_opportunity_complexity_bands() -> None:
    """1-2 reqs → Low; 3-5 → Medium; 6+ → High."""
    user = _user(langs=["Python"], topics=[])

    low = enrich_opportunity(_stub_opp(["A", "B"]), user, use_llm=False, now=NOW)
    medium = enrich_opportunity(_stub_opp(["A", "B", "C", "D"]), user, use_llm=False, now=NOW)
    high = enrich_opportunity(
        _stub_opp(["A", "B", "C", "D", "E", "F", "G"]), user, use_llm=False, now=NOW
    )

    assert low.execution_intel.complexity_to_time_ratio == "Low"
    assert medium.execution_intel.complexity_to_time_ratio == "Medium"
    assert high.execution_intel.complexity_to_time_ratio == "High"


def test_enrich_opportunity_deadman_uses_velocity() -> None:
    """A more-active user should get a later (more relaxed) start date."""
    stub = _stub_opp(["Python"])
    active = _user(langs=["Python"], topics=[], days_since_push=3)
    cold = _user(langs=["Python"], topics=[], days_since_push=200)

    active_opp = enrich_opportunity(stub, active, use_llm=False, now=NOW)
    cold_opp = enrich_opportunity(stub, cold, use_llm=False, now=NOW)

    # Cold user runs at 0.5 h/day vs active user at 3 h/day → much earlier start
    assert (
        cold_opp.execution_intel.recommended_start_date_iso
        < active_opp.execution_intel.recommended_start_date_iso
    )
    assert cold_opp.execution_intel.deadman_switch_alert
    assert active_opp.execution_intel.deadman_switch_alert


def test_enrich_opportunity_overall_fit_blends_trust_and_overlap() -> None:
    """overall_fit should be the average of trust and semantic overlap."""
    stub = _stub_opp(["Python"])
    user = _user(langs=["Python"], topics=[], stars=100, days_since_push=0)
    enriched = enrich_opportunity(stub, user, use_llm=False, now=NOW)

    expected = round(
        (enriched.match_analysis.user_trust_score + enriched.match_analysis.semantic_overlap_score) / 2
    )
    assert enriched.match_analysis.overall_fit_percentage == expected


def test_enrich_opportunity_preserves_metadata_and_id() -> None:
    """The enricher must NOT mutate the metadata block (only analyst fields)."""
    stub = _stub_opp(["Python"])
    user = _user(langs=["Python"], topics=[])
    enriched = enrich_opportunity(stub, user, use_llm=False, now=NOW)
    assert enriched.opportunity_id == stub.opportunity_id
    assert enriched.metadata == stub.metadata
    assert enriched.teammate_matchmaker == stub.teammate_matchmaker
