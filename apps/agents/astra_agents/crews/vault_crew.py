"""Vault crew (USP D) — turns a `ProofOfWork` into a narrated portfolio.

Astra's "Proof-of-Work Vault" doesn't just list a user's GitHub repos — it
writes a one-paragraph blurb for each one explaining what the project shows
about the user. Think of it as an auto-generated portfolio README.

Two paths:
- LLM path runs the creative LLM once per repo with strict bounded prompts.
- Fallback templates a blurb from the repo's metadata (description, language,
  stars, topics). The fallback is intentionally NOT a placeholder — it's
  actually useful even when the LLM is offline.

Output is a `Vault` model from `astra_schemas`, ready to serve to the API and
the Next.js `/profile/[login]` page.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from astra_core import ProofOfWork
from astra_schemas import Vault, VaultEntry, VaultRelevance

logger = logging.getLogger("astra.vault_crew")

# Cap how many repos we narrate. The LLM path is the bottleneck — 8 is enough
# for a portfolio page and keeps the per-request cost predictable.
MAX_VAULT_ENTRIES = 8


def build_vault(
    pow_: ProofOfWork,
    *,
    use_llm: bool = True,
    max_entries: int = MAX_VAULT_ENTRIES,
) -> Vault:
    """Aggregate the user + repos into a `Vault`, narrated either by LLM or templater."""
    repos = sorted(
        pow_.repos,
        key=lambda r: (r.stargazers_count, r.pushed_at or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )[:max_entries]

    narration_source = "fallback"
    entries: list[VaultEntry] = []
    for repo in repos:
        narrative: str | None = None
        if use_llm:
            try:
                narrative = _narrate_repo_with_llm(
                    repo_name=repo.name,
                    description=repo.description,
                    language=repo.language,
                    stars=repo.stargazers_count,
                    topics=repo.topics,
                )
                narration_source = "llm"
            except Exception as exc:  # noqa: BLE001
                logger.warning("vault_crew: LLM narration failed for %s (%s)", repo.full_name, exc)
                narrative = None
        if not narrative:
            narrative = _fallback_narrative(
                repo_name=repo.name,
                description=repo.description,
                language=repo.language,
                stars=repo.stargazers_count,
                topics=repo.topics,
            )
        entries.append(
            VaultEntry(
                repo_full_name=repo.full_name,
                repo_name=repo.name,
                repo_url=repo.html_url,  # type: ignore[arg-type]
                language=repo.language,
                stars=repo.stargazers_count,
                topics=list(repo.topics),
                description=repo.description,
                narrative=narrative,
                relevance=_relevance_for(repo.stargazers_count, len(repo.topics)),
            )
        )

    return Vault(
        user_login=pow_.user.login,
        user_name=pow_.user.name,
        user_url=pow_.user.html_url,  # type: ignore[arg-type]
        bio=pow_.user.bio,
        total_stars=pow_.total_stars,
        languages_top=[lang for lang, _ in pow_.languages_top],
        entries=entries,
        generated_at=datetime.now(timezone.utc),
        narration_source=narration_source,  # type: ignore[arg-type]
    )


def _relevance_for(stars: int, topic_count: int) -> VaultRelevance:
    """Crude relevance bucket — refined by USP A scaffolder later when it
    needs to pick the top-3 proofs against a specific opportunity."""
    if stars >= 25 or topic_count >= 4:
        return "high"
    if stars >= 5 or topic_count >= 1:
        return "medium"
    return "low"


def _fallback_narrative(
    *,
    repo_name: str,
    description: str | None,
    language: str | None,
    stars: int,
    topics: list[str],
) -> str:
    """Templated narrative used when the LLM is disabled or fails.

    Always returns a non-empty string so `VaultEntry.narrative` validates.
    """
    parts: list[str] = []
    if description:
        parts.append(f"{repo_name} — {description.strip().rstrip('.')}.")
    else:
        parts.append(f"{repo_name} is a project in this user's portfolio.")
    tech_bits: list[str] = []
    if language:
        tech_bits.append(f"written in {language}")
    if topics:
        tech_bits.append("topics: " + ", ".join(topics[:5]))
    if tech_bits:
        parts.append("It's " + "; ".join(tech_bits) + ".")
    if stars > 0:
        parts.append(
            f"It has {stars} GitHub star{'s' if stars != 1 else ''} from other developers."
        )
    return " ".join(parts)


def _narrate_repo_with_llm(
    *,
    repo_name: str,
    description: str | None,
    language: str | None,
    stars: int,
    topics: list[str],
) -> str:
    """LLM narration — one repo at a time, strict 2-3 sentence cap.

    Lazy import keeps tests free of CrewAI/LiteLLM unless they explicitly want
    the LLM path.
    """
    from crewai import Agent, Crew, Process, Task

    from astra_agents.llm import get_creative_llm

    desc = description or "(no description)"
    lang = language or "unknown"
    topic_text = ", ".join(topics) if topics else "(none)"

    narrator = Agent(
        role="Proof-of-Work Narrator",
        goal=(
            "Write a 2-3 sentence plain-English description of a GitHub repo "
            "that explains what it demonstrates about the developer."
        ),
        backstory=(
            "You write portfolio blurbs for developers. You are concrete and "
            "concise. You never invent capabilities the data doesn't support. "
            "You write in third person, present tense."
        ),
        llm=get_creative_llm(),
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=(
            f"REPO: {repo_name}\n"
            f"DESCRIPTION: {desc}\n"
            f"PRIMARY LANGUAGE: {lang}\n"
            f"GITHUB STARS: {stars}\n"
            f"TOPICS: {topic_text}\n\n"
            "Write 2-3 sentences (max 80 words) describing what this repo "
            "demonstrates about the developer. Mention the language and at "
            "least one specific detail. No marketing language. No headings, "
            "no bullets, no markdown."
        ),
        expected_output="A 2-3 sentence paragraph in plain text.",
        agent=narrator,
    )
    crew = Crew(agents=[narrator], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    raw = (getattr(result, "raw", None) or str(result)).strip()
    if not raw:
        raise ValueError("Empty LLM output")
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip()
    return raw[:1400]  # VaultEntry.narrative max_length=1500


__all__ = ["build_vault"]
