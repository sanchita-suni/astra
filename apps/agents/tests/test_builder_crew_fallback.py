"""builder_crew fallback tests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astra_agents.crews.builder_crew import (
    default_repo_name,
    pick_template,
    scaffold_to_directory,
    TEMPLATES_DIR,
)
from astra_schemas import (
    ExecutionIntel,
    MatchAnalysis,
    Metadata,
    Opportunity,
    ReadinessEngine,
    ScaffoldResult,
    TeammateMatchmaker,
)

DEADLINE = datetime(2026, 12, 10, tzinfo=timezone.utc)


def _opp(requirements: list[str]) -> Opportunity:
    return Opportunity(
        opportunity_id="test-scaffold",
        metadata=Metadata(
            title="Edge AI Innovation Challenge",
            organization="NVIDIA",
            source="Devpost",
            type="Hackathon",
            mode="Remote",
            deadline_iso=DEADLINE,
            apply_link="https://devpost.com/software/test",  # type: ignore[arg-type]
            raw_requirements=requirements,
        ),
        match_analysis=MatchAnalysis(
            overall_fit_percentage=70,
            semantic_overlap_score=80,
            user_trust_score=60,
            ai_reasoning="Why it fits: strong Python + CV overlap.",
        ),
        execution_intel=ExecutionIntel(
            complexity_to_time_ratio="Medium",
            estimated_hours_required=32,
            recommended_start_date_iso=DEADLINE - timedelta(days=14),
            deadman_switch_alert="Start by Nov 28.",
        ),
        readiness_engine=ReadinessEngine(
            skill_gap_identified=["YOLOv8"],
            bridge_roadmap=[],
        ),
        teammate_matchmaker=TeammateMatchmaker(suggested_super_team=[]),
    )


# ---------------------------------------------------------------------------
# Template picker
# ---------------------------------------------------------------------------


def test_pick_template_ml() -> None:
    assert pick_template(["Python", "TensorFlow", "Raspberry Pi"]) == "python-ml"


def test_pick_template_nextjs() -> None:
    assert pick_template(["React", "Tailwind", "TypeScript"]) == "nextjs-fullstack"


def test_pick_template_fastapi_react() -> None:
    assert pick_template(["FastAPI", "React"]) == "fastapi-react"


def test_pick_template_generic() -> None:
    assert pick_template(["Python"]) == "generic-python"


def test_pick_template_unknown_defaults_generic() -> None:
    assert pick_template(["Haskell"]) == "generic-python"


def test_pick_template_empty_defaults_generic() -> None:
    assert pick_template([]) == "generic-python"


# ---------------------------------------------------------------------------
# Repo name
# ---------------------------------------------------------------------------


def test_default_repo_name_slugified() -> None:
    opp = _opp(["Python"])
    name = default_repo_name(opp)
    assert name == "edge-ai-innovation-challenge-starter"


# ---------------------------------------------------------------------------
# Scaffold to directory
# ---------------------------------------------------------------------------


def test_scaffold_creates_files_and_brief() -> None:
    opp = _opp(["Python", "TensorFlow"])
    with tempfile.TemporaryDirectory() as tmp:
        result = scaffold_to_directory(opp, Path(tmp), use_llm=False)
        assert isinstance(result, ScaffoldResult)
        assert result.template == "python-ml"
        assert result.dry_run is True
        assert result.repo_url is None
        assert result.brief_source == "fallback"
        assert result.brief_markdown
        assert "Edge AI Innovation Challenge" in result.brief_markdown
        # BRIEF.md and the template files should exist
        paths = [f.path for f in result.files]
        assert "BRIEF.md" in paths
        assert "train.py" in paths
        assert "requirements.txt" in paths
        # BRIEF.md.template should NOT be in the output
        assert "BRIEF.md.template" not in paths
        # Files should actually exist on disk
        for f in result.files:
            assert (Path(tmp) / f.path).exists()


def test_scaffold_readme_substitution() -> None:
    opp = _opp(["Python"])
    with tempfile.TemporaryDirectory() as tmp:
        result = scaffold_to_directory(opp, Path(tmp), use_llm=False)
        readme = (Path(tmp) / "README.md").read_text(encoding="utf-8")
        assert "Edge AI Innovation Challenge" in readme
        assert "NVIDIA" in readme
        assert "{opportunity_title}" not in readme
        assert "{organization}" not in readme


def test_scaffold_brief_contains_required_sections() -> None:
    opp = _opp(["Python", "TensorFlow"])
    with tempfile.TemporaryDirectory() as tmp:
        result = scaffold_to_directory(opp, Path(tmp), use_llm=False)
        assert "What you're building" in result.brief_markdown
        assert "Required tech" in result.brief_markdown
        assert "Day-1 task list" in result.brief_markdown
        assert "Deadline math" in result.brief_markdown
