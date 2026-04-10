"""Dry-Run Demo Day (USP B) — judge panel schema.

`judge_crew` runs three persona agents (Industry, Academic, VC) over a user's
project pitch and returns a numeric rubric + per-judge feedback. This file is
the shape every judge run produces — the API serves it, the frontend renders
it as three scorecards plus an overall.

The MVP is single-shot: the user submits a pitch, the judges score it, done.
The plan reserves an upgrade path for multi-turn (judge → question → answer →
final), but the cut-list says single-shot if time is tight, so single-shot is
the contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

JudgePersona = Literal["industry", "academic", "vc"]
RubricSource = Literal["llm", "fallback"]


class _RehearsalBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class RubricBreakdown(_RehearsalBase):
    """The four scoring dimensions every judge fills in (0-25 each)."""

    feasibility: int = Field(ge=0, le=25)
    novelty: int = Field(ge=0, le=25)
    market_fit: int = Field(ge=0, le=25)
    polish: int = Field(ge=0, le=25)


class JudgeScore(_RehearsalBase):
    """One judge's verdict on a pitch."""

    judge: JudgePersona
    judge_name: str = Field(min_length=1, max_length=120)
    rubric: RubricBreakdown
    score: int = Field(
        ge=0,
        le=100,
        description="Sum of the four rubric dimensions (each 0-25, total 0-100).",
    )
    feedback: str = Field(min_length=1, max_length=1500)


class DryRunRequest(_RehearsalBase):
    """The body of POST /opportunities/{id}/dry-run."""

    pitch: str = Field(
        min_length=20,
        max_length=4000,
        description="The 1-3 paragraph project pitch the judges will score.",
    )
    repo_url: HttpUrl | None = Field(
        default=None,
        description="Optional link to the project repo, surfaced in feedback.",
    )


class DryRunRubric(_RehearsalBase):
    """Full output of POST /opportunities/{id}/dry-run."""

    opportunity_id: str = Field(min_length=1)
    pitch: str = Field(min_length=1)
    repo_url: HttpUrl | None = None
    scores: list[JudgeScore] = Field(min_length=1)
    overall_score: int = Field(ge=0, le=100)
    overall_feedback: str = Field(min_length=1, max_length=2000)
    generated_at: datetime
    rubric_source: RubricSource = Field(default="fallback")
