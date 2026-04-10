"""Astra schemas — Pydantic v2 models for the Opportunity Digest contract.

This package is the single source of truth for the shape of every Opportunity
that flows through Astra. FastAPI imports it directly. TypeScript types for the
Next.js frontend are generated from these models via `pydantic-to-typescript`.
"""

from astra_schemas.opportunity import (
    BridgeRoadmapDay,
    ExecutionIntel,
    MatchAnalysis,
    Metadata,
    Opportunity,
    ReadinessEngine,
    Resource,
    ResourceType,
    SuperTeamMember,
    TeammateMatchmaker,
)
from astra_schemas.rehearsal import (
    DryRunRequest,
    DryRunRubric,
    JudgePersona,
    JudgeScore,
    RubricBreakdown,
    RubricSource,
)
from astra_schemas.scaffold import ScaffoldedFile, ScaffoldResult, ScaffoldTemplate
from astra_schemas.user import (
    ExperienceLevel,
    HackathonType,
    QuestionnaireResponse,
    ResumeSkills,
    TimeAvailability,
    UserProfile,
)
from astra_schemas.vault import Vault, VaultEntry, VaultRelevance

__all__ = [
    "BridgeRoadmapDay",
    "DryRunRequest",
    "DryRunRubric",
    "ExecutionIntel",
    "JudgePersona",
    "JudgeScore",
    "MatchAnalysis",
    "Metadata",
    "Opportunity",
    "ReadinessEngine",
    "Resource",
    "ResourceType",
    "RubricBreakdown",
    "RubricSource",
    "ScaffoldResult",
    "ScaffoldTemplate",
    "ScaffoldedFile",
    "SuperTeamMember",
    "TeammateMatchmaker",
    "TimeAvailability",
    "UserProfile",
    "QuestionnaireResponse",
    "ResumeSkills",
    "ExperienceLevel",
    "HackathonType",
    "Vault",
    "VaultEntry",
    "VaultRelevance",
]
