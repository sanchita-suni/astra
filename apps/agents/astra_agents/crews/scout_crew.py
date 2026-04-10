"""Scout crew — the Day 1 proof that the agent loop works end-to-end.

Single agent + single task. Reads the canonical fixture, runs it through
Ollama with a prompt asking the LLM to confirm the structure, and returns a
validated `Opportunity`. If the LLM loop crashes (cold model, parse failure,
network blip) the crew falls back to the raw fixture so callers always get a
valid `Opportunity` back.

Run as a script:
    uv run python -m astra_agents.crews.scout_crew

Every crew in Astra MUST follow this pattern: try the LLM, fall back
deterministically. CrewAI + Ollama tool calling is the #1 risk in the build —
every other code path assumes an `Opportunity` always materializes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from astra_agents.llm import get_default_llm
from astra_schemas import Opportunity

logger = logging.getLogger("astra.scout_crew")

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = REPO_ROOT / "docs" / "sample_digest.json"


def _load_fixture() -> Opportunity:
    return Opportunity.model_validate_json(FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_crew(fixture_text: str) -> Crew:
    scout = Agent(
        role="Opportunity Scout",
        goal=(
            "Validate that a candidate hackathon JSON matches Astra's canonical "
            "Opportunity Digest schema, and return the validated JSON unchanged."
        ),
        backstory=(
            "You are Astra's lead scout. You read raw scraped opportunity data, "
            "verify it matches the contract, and pass it downstream. You never "
            "invent fields, you never reformat keys. Speed and faithfulness over "
            "creativity. If the input is already valid, return it verbatim."
        ),
        llm=get_default_llm(),
        allow_delegation=False,
        verbose=False,
    )

    validate_task = Task(
        description=(
            "The following JSON is a candidate Opportunity Digest. "
            "Confirm every required top-level key is present (opportunity_id, "
            "metadata, match_analysis, execution_intel, readiness_engine, "
            "teammate_matchmaker) and return the JSON object unchanged.\n\n"
            f"INPUT:\n{fixture_text}"
        ),
        expected_output=(
            "A single JSON object matching the Astra Opportunity Digest schema. "
            "No prose, no markdown fences, just the JSON."
        ),
        agent=scout,
    )

    return Crew(
        agents=[scout],
        tasks=[validate_task],
        process=Process.sequential,
        verbose=False,
    )


def run_scout(use_llm: bool = True) -> Opportunity:
    """Run the scout crew end-to-end and return a validated Opportunity.

    The `use_llm=False` path is for tests / Day 1 acceptance when Ollama may
    not be running. The fallback path also fires automatically on any LLM error.
    """
    fixture = _load_fixture()

    if not use_llm:
        logger.info("scout_crew: LLM disabled, returning fixture")
        return fixture

    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")

    try:
        crew = _build_crew(fixture_text)
        result = crew.kickoff()
        # CrewAI returns a CrewOutput in current versions; older versions return a string.
        raw = getattr(result, "raw", None) or str(result)
        # Strip markdown fences if the model adds them despite instructions
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].lstrip()
        # Find the first { ... } JSON object in case the model added preamble
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace == -1 or last_brace == -1:
            raise ValueError(f"No JSON object found in LLM output: {raw[:200]}")
        json_blob = cleaned[first_brace : last_brace + 1]
        # Ensure it parses, then validate via the schema
        json.loads(json_blob)
        return Opportunity.model_validate_json(json_blob)
    except Exception as exc:
        logger.warning("scout_crew: LLM path failed (%s) — falling back to fixture", exc)
        return fixture


def main() -> None:
    """CLI entry: print the validated Opportunity as pretty JSON."""
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    use_llm = "--no-llm" not in sys.argv
    opp = run_scout(use_llm=use_llm)
    print(opp.model_dump_json(indent=2))
    print(
        f"\n[scout_crew] OK — opportunity_id={opp.opportunity_id} "
        f"title={opp.metadata.title!r} (llm={'on' if use_llm else 'off'})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
