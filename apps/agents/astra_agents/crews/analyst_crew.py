"""Analyst crew — turns a stub Opportunity into a fully-enriched one for a user.

This is the heart of Astra's "personal-velocity calibration" wedge:
- semantic overlap between user signal and the opportunity requirements
- weighted trust score from `packages/core/trust_score`
- per-user deadman switch from `packages/core/deadman`
- skill gap (the requirements your profile doesn't already cover)
- LLM-written `ai_reasoning` paragraph (with deterministic fallback)

The output is a **new** `Opportunity` with `match_analysis`, `execution_intel`,
and `readiness_engine.skill_gap_identified` populated. `bridge_roadmap` is left
empty here — that's `roadmap_crew`'s job, kept separate so the two stages can
be tested and run independently.

Every entry point falls back deterministically when the LLM path fails.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from astra_core import (
    DeadmanInputs,
    ProofOfWork,
    compute_deadman_alert,
    compute_trust_score,
)
from astra_schemas import (
    ExecutionIntel,
    MatchAnalysis,
    Opportunity,
    ReadinessEngine,
)

logger = logging.getLogger("astra.analyst_crew")


# ---------------------------------------------------------------------------
# Heuristics — kept tunable at the top so behavior is inspectable
# ---------------------------------------------------------------------------

# Hours estimate per requirement, capped so a long shopping-list doesn't push
# the estimate into infeasible territory.
HOURS_PER_REQUIREMENT = 8
HOURS_MIN = 8
HOURS_MAX = 80

# Complexity bands (number of distinct requirements)
COMPLEXITY_LOW_MAX = 2
COMPLEXITY_MEDIUM_MAX = 5

# Velocity inference from commit recency
VELOCITY_ACTIVE_DAYS = 7
VELOCITY_WARM_DAYS = 30
VELOCITY_HOURS_ACTIVE = 3.0
VELOCITY_HOURS_WARM = 1.5
VELOCITY_HOURS_COLD = 0.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



# Common tech keywords we extract from repo names/descriptions to boost signal.
# Without this, a user with repos named "ml-pipeline" and "react-dashboard"
# would have zero ML/web signal because GitHub only reports the primary language.
_REPO_NAME_TECH_MAP: dict[str, list[str]] = {
    "ml": ["machine learning"], "ai": ["machine learning", "ai"],
    "llm": ["llm", "machine learning"], "gpt": ["llm"],
    "neural": ["deep learning"], "deep": ["deep learning"],
    "tensorflow": ["tensorflow"], "pytorch": ["pytorch"], "keras": ["keras"],
    "react": ["react"], "next": ["next.js"], "vue": ["vue"],
    "flask": ["flask"], "django": ["django"], "fastapi": ["fastapi"],
    "docker": ["docker"], "kubernetes": ["kubernetes"],
    "blockchain": ["blockchain"], "web3": ["web3"],
    "arduino": ["arduino", "iot"], "raspberry": ["raspberry pi"],
    "flutter": ["flutter"], "swift": ["swift"], "kotlin": ["kotlin"],
    "rust": ["rust"], "golang": ["go"],
    "opencv": ["computer vision", "opencv"],
    "nlp": ["nlp", "natural language processing"],
    "data": ["data science"], "analytics": ["data science"],
    "hack": ["hackathon"], "bot": ["automation"],
    "api": ["api", "rest api"], "backend": ["backend"],
    "frontend": ["frontend"], "fullstack": ["full stack"],
    "gen": ["ai"], "voice": ["nlp"], "vision": ["computer vision"],
}


def _user_signal(user: ProofOfWork) -> set[str]:
    """Aggregate everything we know about the user into a case-insensitive token set.

    Sources: languages, topics, bio words, AND tech keywords from repo names/
    descriptions. This catches signal that GitHub's language detection misses
    (e.g., a repo named "ml-pipeline" written in Python).
    """
    tokens: set[str] = set()
    for lang, _count in user.languages_top:
        if lang:
            tokens.add(lang.lower())
    for repo in user.repos:
        if repo.language:
            tokens.add(repo.language.lower())
        for topic in repo.topics:
            tokens.add(topic.lower())
        # Extract tech signal from repo name + description
        name_desc = (repo.name + " " + (repo.description or "")).lower()
        for keyword, skills in _REPO_NAME_TECH_MAP.items():
            if keyword in name_desc:
                tokens.update(skills)
    if user.user.bio:
        bio_lower = user.user.bio.lower()
        tokens.update(t for t in bio_lower.split() if len(t) > 2)
        # Also check bio for tech keywords
        for keyword, skills in _REPO_NAME_TECH_MAP.items():
            if keyword in bio_lower:
                tokens.update(skills)
    return tokens


def _semantic_overlap_pct(requirements: list[str], user: ProofOfWork) -> int:
    """Deterministic Jaccard-like overlap between requirements and user signal.

    The plan calls for FAISS sentence-transformers cosine similarity, but
    sentence-transformers is a 1.5GB cold-start dependency. We compute a
    cheap, deterministic baseline here so the analyst is fully testable
    without the heavy model. The FAISS path is opt-in via `embedder=...`.
    """
    if not requirements:
        return 0
    needed = {r.lower() for r in requirements if r}
    if not needed:
        return 0
    user_tokens = _user_signal(user)
    overlap = len(needed & user_tokens)
    return round((overlap / len(needed)) * 100)


def _skill_gap(requirements: list[str], user: ProofOfWork) -> list[str]:
    """The case-insensitive set difference, but preserving original casing/order."""
    user_tokens = _user_signal(user)
    seen: set[str] = set()
    out: list[str] = []
    for req in requirements:
        key = req.lower()
        if key in user_tokens or key in seen:
            continue
        seen.add(key)
        out.append(req)
    return out


def _estimate_complexity(requirements: list[str]) -> str:
    n = len(requirements)
    if n <= COMPLEXITY_LOW_MAX:
        return "Low"
    if n <= COMPLEXITY_MEDIUM_MAX:
        return "Medium"
    return "High"


def _estimate_hours(requirements: list[str]) -> int:
    n = len(requirements) or 1
    return max(HOURS_MIN, min(HOURS_MAX, n * HOURS_PER_REQUIREMENT))


def _user_avg_hours_per_day(user: ProofOfWork) -> float:
    """Infer focused-hours-per-day from the user's recent commit cadence.

    Active (push within a week)  → 3h/day
    Warm   (push within a month) → 1.5h/day
    Cold   (older / unknown)     → 0.5h/day
    """
    days = user.days_since_last_push
    if days is None:
        return VELOCITY_HOURS_COLD
    if days <= VELOCITY_ACTIVE_DAYS:
        return VELOCITY_HOURS_ACTIVE
    if days <= VELOCITY_WARM_DAYS:
        return VELOCITY_HOURS_WARM
    return VELOCITY_HOURS_COLD


def _build_fallback_reasoning(
    *,
    overall_fit: int,
    overlap_pct: int,
    trust_total: int,
    skill_gap: list[str],
    user_top_langs: list[str],
    requirements: list[str],
) -> str:
    """Templated `ai_reasoning` used when the LLM is disabled or fails."""
    langs_text = ", ".join(user_top_langs[:3]) if user_top_langs else "no public languages detected"
    if not requirements:
        return (
            f"Why it fits: with no listed requirements we default to a "
            f"baseline fit of {overall_fit}% based purely on your trust score "
            f"({trust_total})."
        )
    if not skill_gap:
        return (
            f"Why it fits: your top languages ({langs_text}) already cover "
            f"every listed requirement ({', '.join(requirements)}). Trust "
            f"score {trust_total}, semantic overlap {overlap_pct}% — overall "
            f"fit {overall_fit}%."
        )
    return (
        f"Why it fits: your top languages ({langs_text}) cover {overlap_pct}% "
        f"of the listed requirements; the remaining gaps are "
        f"{', '.join(skill_gap)}. Trust score {trust_total}. Overall fit "
        f"{overall_fit}% — bridge_roadmap will close the gap."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enrich_opportunity(
    stub: Opportunity,
    user: ProofOfWork,
    *,
    use_llm: bool = True,
    now: datetime | None = None,
) -> Opportunity:
    """Replace the placeholder analyst fields on a stub `Opportunity` with real ones.

    `bridge_roadmap` is intentionally NOT populated here — see `roadmap_crew`.
    """
    requirements = list(stub.metadata.raw_requirements)

    trust = compute_trust_score(user)
    overlap_pct = _semantic_overlap_pct(requirements, user)
    skill_gap = _skill_gap(requirements, user)

    overall_fit = round((trust.total + overlap_pct) / 2)
    overall_fit = max(0, min(100, overall_fit))

    estimated_hours = _estimate_hours(requirements)
    complexity = _estimate_complexity(requirements)

    deadman = compute_deadman_alert(
        DeadmanInputs(
            deadline=stub.metadata.deadline_iso,
            estimated_hours_required=estimated_hours,
            user_avg_hours_per_day=_user_avg_hours_per_day(user),
            velocity_multiplier=1.0,
            now=now,
        )
    )

    user_top_langs = [lang for lang, _ in user.languages_top]

    reasoning: str | None = None
    if use_llm:
        try:
            reasoning = _generate_reasoning_with_llm(
                stub=stub,
                user=user,
                overall_fit=overall_fit,
                overlap_pct=overlap_pct,
                trust_total=trust.total,
                skill_gap=skill_gap,
            )
        except Exception as exc:  # noqa: BLE001 — every LLM call must fail safe
            logger.warning("analyst_crew: LLM reasoning failed (%s) — using fallback", exc)
            reasoning = None
    if not reasoning:
        reasoning = _build_fallback_reasoning(
            overall_fit=overall_fit,
            overlap_pct=overlap_pct,
            trust_total=trust.total,
            skill_gap=skill_gap,
            user_top_langs=user_top_langs,
            requirements=requirements,
        )

    enriched = stub.model_copy(
        update={
            "match_analysis": MatchAnalysis(
                overall_fit_percentage=overall_fit,
                semantic_overlap_score=overlap_pct,
                user_trust_score=trust.total,
                ai_reasoning=reasoning,
            ),
            "execution_intel": ExecutionIntel(
                complexity_to_time_ratio=complexity,  # type: ignore[arg-type]
                estimated_hours_required=estimated_hours,
                recommended_start_date_iso=deadman.recommended_start,
                deadman_switch_alert=deadman.alert_text,
            ),
            "readiness_engine": ReadinessEngine(
                skill_gap_identified=skill_gap,
                bridge_roadmap=list(stub.readiness_engine.bridge_roadmap),
            ),
        }
    )
    return enriched


# ---------------------------------------------------------------------------
# LLM path — isolated so tests can monkeypatch or skip it cleanly
# ---------------------------------------------------------------------------


def _generate_reasoning_with_llm(
    *,
    stub: Opportunity,
    user: ProofOfWork,
    overall_fit: int,
    overlap_pct: int,
    trust_total: int,
    skill_gap: list[str],
) -> str:
    """Ask the LLM to write a 2-3 sentence `ai_reasoning` paragraph.

    Imported lazily so tests that don't touch the LLM don't drag CrewAI
    + LiteLLM + Ollama into the import graph.
    """
    from crewai import Agent, Crew, Process, Task

    from astra_agents.llm import get_default_llm

    user_top_langs = ", ".join([lang for lang, _ in user.languages_top[:5]]) or "(none)"
    skill_gap_text = ", ".join(skill_gap) if skill_gap else "(none — full coverage)"
    requirements_text = ", ".join(stub.metadata.raw_requirements) or "(unspecified)"

    analyst = Agent(
        role="Hackathon Fit Analyst",
        goal=(
            "Explain why a hackathon opportunity is or isn't a fit for the user "
            "in 2-3 plain-English sentences. Be specific, cite the numbers."
        ),
        backstory=(
            "You are Astra's analyst. You are blunt and quantitative. You never "
            "invent numbers — you reuse the ones provided. You write for an "
            "ambitious solo student, not for a board meeting."
        ),
        llm=get_default_llm(),
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=(
            f"OPPORTUNITY: {stub.metadata.title} ({stub.metadata.organization})\n"
            f"REQUIREMENTS: {requirements_text}\n"
            f"USER TOP LANGUAGES: {user_top_langs}\n"
            f"COMPUTED SCORES — overall_fit={overall_fit}%, semantic_overlap={overlap_pct}%, "
            f"trust_score={trust_total}\n"
            f"SKILL GAP: {skill_gap_text}\n\n"
            "Write 2-3 sentences starting with 'Why it fits:' that explain the "
            "fit using the numbers above. Mention specific requirements and "
            "the user's actual languages. No bullet points, no headings."
        ),
        expected_output="A single paragraph starting with 'Why it fits:'",
        agent=analyst,
    )
    crew = Crew(agents=[analyst], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    raw = (getattr(result, "raw", None) or str(result)).strip()
    if not raw:
        raise ValueError("Empty LLM output")
    # Trim accidental code-fence wrapping
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip()
        if raw.lower().startswith("text"):
            raw = raw[4:].lstrip()
    return raw[:1900]  # MatchAnalysis.ai_reasoning has max_length=2000


def main() -> None:  # pragma: no cover — CLI smoke
    """CLI: enrich the demo fixture against a fake user, print the result."""
    import json
    import sys
    from pathlib import Path

    from astra_github_client import RepoSummary, UserSummary

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    fixture_path = Path(__file__).resolve().parents[4] / "docs" / "sample_digest.json"
    stub = Opportunity.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    fake_user = ProofOfWork(
        user=UserSummary(
            login="demo",
            name="Demo Dev",
            bio="ML hobbyist",
            public_repos=8,
            followers=20,
            html_url="https://github.com/demo",
        ),
        repos=[
            RepoSummary(
                full_name="demo/edge-cv",
                name="edge-cv",
                language="Python",
                stargazers_count=12,
                html_url="https://github.com/demo/edge-cv",
                topics=["raspberry-pi", "tensorflow"],
            )
        ],
        languages_top=[("Python", 8)],
        total_stars=12,
        days_since_last_push=4,
    )

    use_llm = "--no-llm" not in sys.argv
    enriched = enrich_opportunity(stub, fake_user, use_llm=use_llm)
    print(json.dumps(enriched.model_dump(mode="json"), indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
