"""Builder crew (USP A) — Bridge-to-Build scaffolder.

Three jobs:
1. **Pick a template** for the opportunity from the four hand-curated starters
   under `templates/` (`python-ml`, `nextjs-fullstack`, `fastapi-react`,
   `generic-python`). Heuristic-driven so it's fully testable without an LLM.
2. **Generate a BRIEF.md** that ties the chosen template to the specific
   opportunity — title, deadline, required stack, Day-1 task list, bridge
   summary, deadman alert. Deterministic templater is the default; the LLM
   can rewrite the "What you're building" paragraph if available.
3. **Scaffold the files** — either to a local directory (testable, no
   network) or to a real GitHub repo via PyGithub (the live demo path).

The output is a `ScaffoldResult` from `astra_schemas`. Tests use the
directory mode; the API uses the GitHub mode by default.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from astra_github_client import GitHubClient
from astra_schemas import (
    Opportunity,
    ScaffoldResult,
    ScaffoldTemplate,
    ScaffoldedFile,
)

logger = logging.getLogger("astra.builder_crew")

# Resolve the templates dir relative to the repo root. The repo root is the
# parent of `apps/agents/astra_agents/crews/builder_crew.py` walked up 4 levels.
REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = REPO_ROOT / "templates"

# The placeholder file inside each template that gets rewritten to BRIEF.md.
BRIEF_PLACEHOLDER_NAME = "BRIEF.md.template"


# ---------------------------------------------------------------------------
# Template selection — keyword heuristics (deterministic, fully testable)
# ---------------------------------------------------------------------------

ML_KEYWORDS = {
    "tensorflow", "pytorch", "scikit-learn", "scikit learn", "sklearn",
    "machine learning", "ml", "ai", "deep learning", "neural",
    "transformers", "huggingface", "hugging face", "yolov8", "yolo",
    "computer vision", "cv", "nlp", "keras", "jax", "diffusion",
    "tensorrt", "onnx", "pandas", "numpy",
}

REACT_KEYWORDS = {
    "react", "next.js", "nextjs", "next", "vite", "frontend",
    "vue", "svelte", "tailwind", "ui", "javascript", "typescript",
}

API_KEYWORDS = {
    "fastapi", "rest api", "api", "backend", "django", "flask",
    "express", "graphql", "starlette",
}

PYTHON_KEYWORDS = {"python", "py"}


def pick_template(requirements: list[str]) -> ScaffoldTemplate:
    """Choose a starter template from the opportunity's required tech list.

    Priority:
        1. has both react/frontend AND api/backend signals → fastapi-react
        2. has ML signals                                  → python-ml
        3. has react/frontend signals only                 → nextjs-fullstack
        4. has python (or anything else)                   → generic-python
    """
    tokens = {r.strip().lower() for r in requirements if r}
    # Multi-word keywords use substring matching over the joined string.
    # Short keywords (<=3 chars, e.g. "ai", "ml", "cv", "py") need
    # word-boundary matching to avoid "ai" in "tailwind".
    joined = " ".join(tokens)

    def _has_any(keywords: set[str]) -> bool:
        for kw in keywords:
            if len(kw) <= 3:
                if re.search(r"\b" + re.escape(kw) + r"\b", joined):
                    return True
            elif kw in joined:
                return True
        return False

    has_ml = _has_any(ML_KEYWORDS)
    has_react = _has_any(REACT_KEYWORDS)
    has_api = _has_any(API_KEYWORDS)
    has_python = _has_any(PYTHON_KEYWORDS) or has_ml or has_api

    if has_react and has_api:
        return "fastapi-react"
    if has_ml:
        return "python-ml"
    if has_react:
        return "nextjs-fullstack"
    if has_python:
        return "generic-python"
    return "generic-python"


# ---------------------------------------------------------------------------
# Brief generation — deterministic templater + optional LLM upgrade
# ---------------------------------------------------------------------------


def _slugify(text: str, *, max_len: int = 60) -> str:
    """Repo-safe slug from a free-text title."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    if not s:
        s = "starter"
    return s[:max_len].rstrip("-") or "starter"


def default_repo_name(opp: Opportunity) -> str:
    """`<slugified-title>-starter` — what we name the GitHub repo if not given."""
    return f"{_slugify(opp.metadata.title)}-starter"


def _summarize_bridge(opp: Opportunity) -> str:
    days = opp.readiness_engine.bridge_roadmap
    if not days:
        return "_(no skill gap detected — go straight to the build.)_"
    lines = [f"- **Day {d.day} — {d.focus}**" for d in days[:7]]
    return "\n".join(lines)


def _build_fallback_brief(opp: Opportunity, *, template: ScaffoldTemplate) -> str:
    """Templated BRIEF.md that works even when the LLM is offline.

    Uses the data we already have on the Opportunity object — title, deadline,
    requirements, ai_reasoning, bridge_roadmap, deadman alert. Always returns
    a non-empty markdown string so `ScaffoldResult.brief_markdown` validates.
    """
    deadline = opp.metadata.deadline_iso
    deadline_str = deadline.date().isoformat() if isinstance(deadline, datetime) else str(deadline)
    requirements_block = (
        "\n".join(f"- {r}" for r in opp.metadata.raw_requirements)
        if opp.metadata.raw_requirements
        else "- (none listed — confirm the call for proposals before you start)"
    )
    skill_gap_block = (
        ", ".join(opp.readiness_engine.skill_gap_identified)
        if opp.readiness_engine.skill_gap_identified
        else "_(none — your existing stack already covers the requirements.)_"
    )
    bridge_block = _summarize_bridge(opp)

    return f"""# {opp.metadata.title}

> **{opp.metadata.organization}** — {opp.metadata.source} · {opp.metadata.mode}
> Deadline **{deadline_str}** · Estimated effort **{opp.execution_intel.estimated_hours_required}h** ({opp.execution_intel.complexity_to_time_ratio} complexity)
> Apply: <{opp.metadata.apply_link}>

## What you're building

{opp.match_analysis.ai_reasoning}

## Required tech

{requirements_block}

## Skill gap to close

{skill_gap_block}

## Day-1 task list

1. Get the `{template}` template running locally — verify the hello-world from the README boots.
2. Pull one real input from the problem domain into the project (a CSV, an API call, a sample dataset).
3. Wire that input through the smallest possible end-to-end loop. **Push your first commit before you go to bed.**
4. Bookmark the apply link above and skim the official rules — note any submission gotchas.

## Bridge roadmap (auto-generated)

{bridge_block}

## Deadline math

{opp.execution_intel.deadman_switch_alert}

---
_Brief scaffolded by **Astra**. Edit freely — this is your repo now._
"""


def generate_brief(
    opp: Opportunity,
    *,
    template: ScaffoldTemplate,
    use_llm: bool = True,
) -> tuple[str, str]:
    """Build the BRIEF.md text. Returns `(markdown, source)` where source is
    `"llm"` or `"fallback"`."""
    if use_llm:
        try:
            llm_paragraph = _generate_what_youre_building_with_llm(opp)
            if llm_paragraph:
                # Patch the LLM paragraph into the templated brief by replacing
                # the analyst's reasoning section. Keeps everything else stable.
                templated = _build_fallback_brief(opp, template=template)
                fallback_para = opp.match_analysis.ai_reasoning
                if fallback_para and fallback_para in templated:
                    return templated.replace(fallback_para, llm_paragraph, 1), "llm"
                return templated, "llm"
        except Exception as exc:  # noqa: BLE001
            logger.warning("builder_crew: LLM brief failed (%s) — using fallback", exc)
    return _build_fallback_brief(opp, template=template), "fallback"


def _generate_what_youre_building_with_llm(opp: Opportunity) -> str:
    """Lazy-imported LLM call — produces a 3-4 sentence problem framing."""
    from crewai import Agent, Crew, Process, Task

    from astra_agents.llm import get_creative_llm

    requirements = ", ".join(opp.metadata.raw_requirements) or "(unspecified)"
    deadline = (
        opp.metadata.deadline_iso.date().isoformat()
        if isinstance(opp.metadata.deadline_iso, datetime)
        else str(opp.metadata.deadline_iso)
    )

    builder = Agent(
        role="Hackathon Brief Writer",
        goal=(
            "Write a 3-4 sentence framing of what the user is going to build, "
            "tying their stack to the opportunity's requirements."
        ),
        backstory=(
            "You write per-project briefs for solo hackathon developers. You "
            "are concrete, motivating, and you never invent requirements. You "
            "write in second person ('you'll build…')."
        ),
        llm=get_creative_llm(),
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description=(
            f"OPPORTUNITY: {opp.metadata.title} ({opp.metadata.organization})\n"
            f"DEADLINE: {deadline}\n"
            f"REQUIRED STACK: {requirements}\n"
            f"WHY IT FITS THE USER: {opp.match_analysis.ai_reasoning}\n\n"
            "Write 3-4 sentences (max 110 words) describing what the user "
            "should build for this opportunity. Mention at least one specific "
            "requirement from the list. No headings, no bullets, no markdown."
        ),
        expected_output="A 3-4 sentence paragraph in plain text.",
        agent=builder,
    )
    crew = Crew(agents=[builder], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    raw = (getattr(result, "raw", None) or str(result)).strip()
    if not raw:
        raise ValueError("Empty LLM output")
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip()
    return raw[:1500]


# ---------------------------------------------------------------------------
# File scaffolding
# ---------------------------------------------------------------------------


def _walk_template_files(template: ScaffoldTemplate, templates_root: Path) -> list[Path]:
    template_dir = templates_root / template
    if not template_dir.exists():
        raise FileNotFoundError(f"Template not found: {template_dir}")
    return sorted(p for p in template_dir.rglob("*") if p.is_file())


def _render_file(
    src_path: Path,
    rel_path: Path,
    *,
    opp: Opportunity,
    brief_markdown: str,
) -> tuple[str, str]:
    """Return `(target_rel_path, content_text)` for one template file."""
    if rel_path.name == BRIEF_PLACEHOLDER_NAME:
        target = (rel_path.parent / "BRIEF.md").as_posix()
        return target, brief_markdown

    content = src_path.read_text(encoding="utf-8")
    if rel_path.name == "README.md":
        content = content.replace("{opportunity_title}", opp.metadata.title).replace(
            "{organization}", opp.metadata.organization
        )
    return rel_path.as_posix(), content


def scaffold_to_directory(
    opp: Opportunity,
    target_dir: Path,
    *,
    templates_root: Path = TEMPLATES_DIR,
    use_llm: bool = False,
    repo_name: str | None = None,
) -> ScaffoldResult:
    """Materialize the chosen template to a local directory. No network.

    The default `use_llm=False` keeps tests fast. The API path uses
    `scaffold_to_github` which defaults to `use_llm=True`.
    """
    template = pick_template(opp.metadata.raw_requirements)
    brief_markdown, brief_source = generate_brief(opp, template=template, use_llm=use_llm)

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    files: list[ScaffoldedFile] = []
    template_dir = templates_root / template
    for src in _walk_template_files(template, templates_root):
        rel = src.relative_to(template_dir)
        target_rel, content = _render_file(
            src, rel, opp=opp, brief_markdown=brief_markdown
        )
        dest = target_dir / target_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        files.append(
            ScaffoldedFile(path=target_rel, bytes=len(content.encode("utf-8")))
        )

    return ScaffoldResult(
        opportunity_id=opp.opportunity_id,
        template=template,
        repo_name=repo_name or default_repo_name(opp),
        repo_url=None,
        brief_markdown=brief_markdown,
        files=files,
        created_at=datetime.now(timezone.utc),
        dry_run=True,
        brief_source=brief_source,  # type: ignore[arg-type]
    )


def scaffold_to_github(
    opp: Opportunity,
    *,
    github: GitHubClient,
    repo_name: str | None = None,
    private: bool = False,
    use_llm: bool = True,
    templates_root: Path = TEMPLATES_DIR,
) -> ScaffoldResult:
    """Scaffold to a real GitHub repo under the authenticated user.

    Creates the repo with `auto_init=True` so the default branch exists, then
    pushes each template file via PyGithub's `create_file` API. The brief is
    pushed as `BRIEF.md`.
    """
    template = pick_template(opp.metadata.raw_requirements)
    brief_markdown, brief_source = generate_brief(opp, template=template, use_llm=use_llm)
    name = repo_name or default_repo_name(opp)

    repo_summary = github.create_repo_for_authenticated_user(
        name=name,
        description=f"Astra Bridge-to-Build starter for {opp.metadata.title}",
        private=private,
        auto_init=True,
    )

    files: list[ScaffoldedFile] = []
    template_dir = templates_root / template
    for src in _walk_template_files(template, templates_root):
        rel = src.relative_to(template_dir)
        target_rel, content = _render_file(
            src, rel, opp=opp, brief_markdown=brief_markdown
        )
        try:
            github.create_file_in_repo(
                repo_summary.full_name,
                target_rel,
                content,
                message=f"Astra scaffold: {target_rel}",
            )
            files.append(
                ScaffoldedFile(path=target_rel, bytes=len(content.encode("utf-8")))
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("scaffold: failed to push %s: %s", target_rel, exc)

    return ScaffoldResult(
        opportunity_id=opp.opportunity_id,
        template=template,
        repo_name=name,
        repo_url=repo_summary.html_url,  # type: ignore[arg-type]
        brief_markdown=brief_markdown,
        files=files,
        created_at=datetime.now(timezone.utc),
        dry_run=False,
        brief_source=brief_source,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def main() -> None:  # pragma: no cover
    """`python -m astra_agents.crews.builder_crew` — scaffold the demo fixture
    into a temp dir and print the brief."""
    import json

    fixture_path = REPO_ROOT / "docs" / "sample_digest.json"
    opp = Opportunity.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="astra-scaffold-") as tmp:
        result = scaffold_to_directory(opp, Path(tmp))
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        print(f"\n[builder_crew] scaffolded {len(result.files)} files into {tmp}")
        # Clean up after printing — tempdir auto-removes
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = [
    "default_repo_name",
    "generate_brief",
    "pick_template",
    "scaffold_to_directory",
    "scaffold_to_github",
    "TEMPLATES_DIR",
]
