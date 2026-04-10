"""Judge crew (USP B) — Dry-Run Demo Day single-shot rubric.

Three judge personas score a user's pitch for a hackathon opportunity:

- **Industry** (weights feasibility): "Can a team actually ship this in a weekend?"
- **Academic** (weights novelty): "Is this research-worthy or just CRUD?"
- **VC** (weights market fit): "Who's the user and is this a real problem?"

Each judge fills a `RubricBreakdown` (feasibility/novelty/market_fit/polish,
each 0-25, sum = score 0-100) and writes 2-4 sentences of feedback. The
three scores are averaged into an `overall_score`.

The deterministic fallback uses keyword heuristics + length proxies so the
endpoint always returns a usable rubric even when the LLM is down.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from astra_schemas import (
    DryRunRubric,
    JudgePersona,
    JudgeScore,
    Opportunity,
    RubricBreakdown,
)

logger = logging.getLogger("astra.judge_crew")

# How many words in the pitch before we stop rewarding "polish" for length.
POLISH_SATURATION_WORDS = 300

# Persona metadata used by both fallback and LLM paths.
JUDGE_PROFILES: dict[JudgePersona, dict[str, str]] = {
    "industry": {
        "name": "Priya Mehta (Industry)",
        "backstory": (
            "Ex-CTO of a dev-tools startup. You care most about whether a team "
            "can actually ship something working in a weekend. You smell over-"
            "scoped projects a mile away and you penalize them hard."
        ),
        "weight_bias": "feasibility",
    },
    "academic": {
        "name": "Dr. James Chen (Academic)",
        "backstory": (
            "CS professor specializing in HCI. You are bored by CRUD apps and "
            "reward genuine novelty — unusual data sources, creative use of "
            "constraints, or non-obvious problem framings."
        ),
        "weight_bias": "novelty",
    },
    "vc": {
        "name": "Sarah Kim (VC)",
        "backstory": (
            "Early-stage VC who has sat on 200 hackathon panels. You ask 'who "
            "is the user?' and 'is this a real problem?' before anything else. "
            "You love projects that name a specific audience."
        ),
        "weight_bias": "market_fit",
    },
}


# ---------------------------------------------------------------------------
# Deterministic fallback — keyword heuristics + pitch quality proxies
# ---------------------------------------------------------------------------


def _count_keyword_hits(text: str, keywords: set[str]) -> int:
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


_FEASIBILITY_WORDS = {"mvp", "prototype", "demo", "deploy", "ship", "api", "working", "build"}
_NOVELTY_WORDS = {"novel", "unique", "innovative", "creative", "first", "new approach", "unsolved"}
_MARKET_WORDS = {"user", "customer", "problem", "market", "audience", "pain point", "need"}


def _heuristic_rubric(
    pitch: str,
    opp: Opportunity,
    *,
    persona: JudgePersona,
    has_repo: bool,
) -> tuple[RubricBreakdown, str]:
    """Score a pitch via keyword heuristics. Cheap, deterministic, always valid."""
    joined = f"{pitch} {' '.join(opp.metadata.raw_requirements)}".lower()
    word_count = len(pitch.split())
    profile = JUDGE_PROFILES[persona]

    # Baseline: 10/25 per dimension (uninspiring but competent)
    feasibility = 10 + min(5, _count_keyword_hits(joined, _FEASIBILITY_WORDS))
    novelty = 10 + min(5, _count_keyword_hits(joined, _NOVELTY_WORDS))
    market_fit = 10 + min(5, _count_keyword_hits(joined, _MARKET_WORDS))
    polish = 10 + min(5, round(min(word_count, POLISH_SATURATION_WORDS) / POLISH_SATURATION_WORDS * 5))

    # Having a repo bumps feasibility + polish by 2 each.
    if has_repo:
        feasibility = min(25, feasibility + 2)
        polish = min(25, polish + 2)

    # Apply persona bias: the dimension that matches weight_bias gets +3.
    bias = profile["weight_bias"]
    if bias == "feasibility":
        feasibility = min(25, feasibility + 3)
    elif bias == "novelty":
        novelty = min(25, novelty + 3)
    elif bias == "market_fit":
        market_fit = min(25, market_fit + 3)

    rubric = RubricBreakdown(
        feasibility=feasibility,
        novelty=novelty,
        market_fit=market_fit,
        polish=polish,
    )
    score = feasibility + novelty + market_fit + polish

    # Templated feedback
    feedback = (
        f"As {profile['name']}, I scored this {score}/100. "
        f"Feasibility ({feasibility}/25) — "
        f"{'good scoping' if feasibility >= 15 else 'scope feels too wide'}. "
        f"Novelty ({novelty}/25) — "
        f"{'interesting angle' if novelty >= 15 else 'could push the framing further'}. "
        f"Market fit ({market_fit}/25) — "
        f"{'clear audience' if market_fit >= 15 else 'who is this for?'}. "
        f"Polish ({polish}/25) — "
        f"{'the pitch reads well' if polish >= 15 else 'more detail would help'}."
    )
    return rubric, feedback


def _fallback_overall_feedback(scores: list[JudgeScore], overall: int) -> str:
    if overall >= 75:
        return f"Strong entry across the board ({overall}/100). Ship it."
    if overall >= 50:
        return (
            f"Decent foundation ({overall}/100). The judges want to see sharper "
            f"scoping and a clearer target user before submission."
        )
    return (
        f"Needs work ({overall}/100). Focus on: who is the user, what is the "
        f"smallest thing you can demo, and why is this approach not CRUD."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_dry_run(
    opp: Opportunity,
    pitch: str,
    repo_url: str | None = None,
    *,
    use_llm: bool = True,
) -> DryRunRubric:
    """Run the three-judge panel over a pitch and return a scored rubric."""
    has_repo = bool(repo_url)
    personas: list[JudgePersona] = ["industry", "academic", "vc"]
    scores: list[JudgeScore] = []
    rubric_source = "fallback"

    for persona in personas:
        rubric: RubricBreakdown | None = None
        feedback: str | None = None

        if use_llm:
            try:
                rubric, feedback = _judge_with_llm(
                    persona=persona, pitch=pitch, opp=opp, repo_url=repo_url
                )
                rubric_source = "llm"
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "judge_crew: LLM scoring failed for %s (%s) — fallback", persona, exc
                )

        if rubric is None or feedback is None:
            rubric, feedback = _heuristic_rubric(
                pitch, opp, persona=persona, has_repo=has_repo
            )

        score = rubric.feasibility + rubric.novelty + rubric.market_fit + rubric.polish
        scores.append(
            JudgeScore(
                judge=persona,
                judge_name=JUDGE_PROFILES[persona]["name"],
                rubric=rubric,
                score=score,
                feedback=feedback,
            )
        )

    overall_score = round(sum(s.score for s in scores) / len(scores))
    overall_feedback = _fallback_overall_feedback(scores, overall_score)

    return DryRunRubric(
        opportunity_id=opp.opportunity_id,
        pitch=pitch,
        repo_url=repo_url,  # type: ignore[arg-type]
        scores=scores,
        overall_score=overall_score,
        overall_feedback=overall_feedback,
        generated_at=datetime.now(timezone.utc),
        rubric_source=rubric_source,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


def _judge_with_llm(
    *,
    persona: JudgePersona,
    pitch: str,
    opp: Opportunity,
    repo_url: str | None,
) -> tuple[RubricBreakdown, str]:
    """Single judge, single-shot: produce rubric + feedback via CrewAI."""
    from crewai import Agent, Crew, Process, Task

    from astra_agents.llm import get_creative_llm

    profile = JUDGE_PROFILES[persona]
    requirements = ", ".join(opp.metadata.raw_requirements) or "(none)"
    repo_line = f"\nPROJECT REPO: {repo_url}" if repo_url else ""

    judge = Agent(
        role=f"Hackathon Judge ({profile['name']})",
        goal=(
            "Score a hackathon pitch on four dimensions (feasibility, novelty, "
            "market_fit, polish) each 0-25, and write 2-4 sentences of feedback. "
            "Output STRICT JSON."
        ),
        backstory=profile["backstory"],
        llm=get_creative_llm(),
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=(
            f"HACKATHON: {opp.metadata.title} ({opp.metadata.organization})\n"
            f"REQUIRED TECH: {requirements}{repo_line}\n\n"
            f"PITCH:\n{pitch}\n\n"
            "Respond with a single JSON object:\n"
            '{"feasibility": <0-25>, "novelty": <0-25>, "market_fit": <0-25>, '
            '"polish": <0-25>, "feedback": "<2-4 sentences>"}\n'
            "No markdown, no prose before/after. Just the JSON."
        ),
        expected_output="A JSON object with feasibility, novelty, market_fit, polish, feedback.",
        agent=judge,
    )
    crew = Crew(agents=[judge], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    raw = (getattr(result, "raw", None) or str(result)).strip()

    return _parse_judge_json(raw)


def _parse_judge_json(raw: str) -> tuple[RubricBreakdown, str]:
    """Parse the LLM's JSON output into a validated rubric + feedback.

    Raises on invalid JSON so the caller falls back to heuristics.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").lstrip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in judge output: {raw[:200]}")
    data: dict[str, Any] = json.loads(cleaned[start : end + 1])

    def _clamp(key: str) -> int:
        return max(0, min(25, int(data.get(key, 10))))

    rubric = RubricBreakdown(
        feasibility=_clamp("feasibility"),
        novelty=_clamp("novelty"),
        market_fit=_clamp("market_fit"),
        polish=_clamp("polish"),
    )
    feedback = str(data.get("feedback", "No feedback provided."))[:1400]
    if not feedback:
        feedback = "No feedback provided."
    return rubric, feedback


__all__ = ["run_dry_run"]
