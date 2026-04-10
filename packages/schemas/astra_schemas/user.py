"""User profile, questionnaire, and resume schemas.

These models power the auth/profile/personalization layer that turns Astra
from a demo into a real product. The user's skills come from three sources:

1. **GitHub** — languages, topics, commit cadence (via `ProofOfWork`)
2. **Resume** — uploaded PDF → keyword-extracted skills + experience
3. **Questionnaire** — self-reported experience level, interests, availability

The personalized feed ranker combines all three to score opportunities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]

HackathonType = Literal[
    "ai-ml",
    "web",
    "mobile",
    "hardware",
    "blockchain",
    "data",
    "social-impact",
    "open",
]

TimeAvailability = Literal["5", "10", "15", "20", "30", "40+"]


class _UserBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class QuestionnaireResponse(_UserBase):
    """Onboarding questionnaire answers."""

    experience_level: ExperienceLevel
    preferred_types: list[HackathonType] = Field(default_factory=list)
    skills_to_learn: list[str] = Field(default_factory=list)
    hours_per_week: TimeAvailability = "10"


class ResumeSkills(_UserBase):
    """Skills extracted from an uploaded resume PDF."""

    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    experience_summary: str = ""
    extraction_source: Literal["keyword", "llm"] = "keyword"


class UserProfile(_UserBase):
    """Full user profile served by the API and rendered by the frontend."""

    user_id: str = Field(min_length=1)
    github_login: str = Field(min_length=1, max_length=120)
    github_name: str | None = None
    github_avatar_url: str | None = None
    email: str | None = None
    questionnaire: QuestionnaireResponse | None = None
    resume: ResumeSkills | None = None
    created_at: datetime
    updated_at: datetime
