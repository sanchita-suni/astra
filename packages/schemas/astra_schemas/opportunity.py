"""The canonical Opportunity Digest schema.

This module defines every field that an Opportunity carries through Astra. If
something isn't here, it doesn't exist. Every other component (FastAPI, the
CrewAI crews, the Next.js frontend, the scrapers) consumes this schema.

Round-trip-test the canonical fixture at `docs/sample_digest.json` against this
module via `tests/test_roundtrip.py` — that test is the contract lock.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

# ---------------------------------------------------------------------------
# Enums (kept as Literals so JSON Schema is self-explanatory and TS generation
# produces clean string-union types instead of opaque enums)
# ---------------------------------------------------------------------------

OpportunityType = Literal["Hackathon", "Internship", "Fellowship", "Grant"]
OpportunityMode = Literal["Remote", "In-Person", "Hybrid"]
ComplexityRatio = Literal["Low", "Medium", "High"]
ResourceType = Literal["Video", "Doc", "Repo", "Course", "Article"]


class _AstraBase(BaseModel):
    """Shared base config — strict on extras, alias-friendly, JSON-mode safe."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        json_schema_extra={"additionalProperties": False},
    )


# ---------------------------------------------------------------------------
# Submodels — order: leaves first, root last
# ---------------------------------------------------------------------------


class Resource(_AstraBase):
    """A single learning resource inside one day of the bridge roadmap."""

    type: ResourceType
    title: str = Field(min_length=1, max_length=200)
    url: HttpUrl


class BridgeRoadmapDay(_AstraBase):
    """One day of the 7-day bridge roadmap that closes a skill gap."""

    day: int = Field(ge=1, le=14, description="Day number in the roadmap (1-indexed).")
    focus: str = Field(min_length=1, max_length=200)
    resources: list[Resource] = Field(min_length=1)


class ReadinessEngine(_AstraBase):
    """Skill-gap analysis + the bridge roadmap that closes it."""

    skill_gap_identified: list[str] = Field(default_factory=list)
    bridge_roadmap: list[BridgeRoadmapDay] = Field(default_factory=list)


class SuperTeamMember(_AstraBase):
    """A single suggested teammate inside the matchmaker output."""

    user_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    role_filled: str = Field(min_length=1, max_length=200)
    compatibility_score: int = Field(ge=0, le=100)


class TeammateMatchmaker(_AstraBase):
    """The suggested super-team for this opportunity.

    Note: this section may be empty for opportunities that don't need teams,
    or where Astra has not yet computed a match. Cut from the V1 build but
    kept on the schema so the contract is forward-compatible.
    """

    suggested_super_team: list[SuperTeamMember] = Field(default_factory=list)


class Metadata(_AstraBase):
    """Raw, normalized metadata about the opportunity itself."""

    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=100, description="Devpost, MLH, Unstop, etc.")
    type: OpportunityType
    mode: OpportunityMode
    deadline_iso: datetime
    apply_link: HttpUrl
    raw_requirements: list[str] = Field(default_factory=list)


class MatchAnalysis(_AstraBase):
    """Why this opportunity fits the user, with quantified scores."""

    overall_fit_percentage: int = Field(ge=0, le=100)
    semantic_overlap_score: int = Field(ge=0, le=100)
    user_trust_score: int = Field(ge=0, le=100)
    ai_reasoning: str = Field(min_length=1, max_length=2000)


class ExecutionIntel(_AstraBase):
    """When and how to start, calibrated to the user's velocity."""

    complexity_to_time_ratio: ComplexityRatio
    estimated_hours_required: int = Field(ge=1, le=1000)
    recommended_start_date_iso: datetime
    deadman_switch_alert: str = Field(min_length=1, max_length=1000)


class Opportunity(_AstraBase):
    """The canonical Opportunity Digest — top-level shape served by every API."""

    opportunity_id: str = Field(min_length=1)
    metadata: Metadata
    match_analysis: MatchAnalysis
    execution_intel: ExecutionIntel
    readiness_engine: ReadinessEngine
    teammate_matchmaker: TeammateMatchmaker
