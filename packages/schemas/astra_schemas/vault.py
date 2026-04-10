"""Proof-of-Work Vault schema (USP D).

The Vault is the auto-narrated portfolio: the user's GitHub repos turned into
plain-English blurbs by `vault_crew`. This file is the contract for that
output — the FastAPI `GET /users/{login}/vault` endpoint serves it and the
Next.js `/profile/[login]` page renders it.

Why this lives in `astra_schemas` (and not in the agents app):
the frontend reads the shape too, and we keep one source of truth so
TypeScript types stay regenerable from Pydantic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

VaultRelevance = Literal["high", "medium", "low"]


class _VaultBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class VaultEntry(_VaultBase):
    """One narrated repo. The narrative is the part the LLM writes."""

    repo_full_name: str = Field(min_length=1, max_length=200)
    repo_name: str = Field(min_length=1, max_length=120)
    repo_url: HttpUrl
    language: str | None = None
    stars: int = Field(ge=0)
    topics: list[str] = Field(default_factory=list)
    description: str | None = None
    narrative: str = Field(
        min_length=1,
        max_length=1500,
        description="Plain-English summary of what this repo demonstrates.",
    )
    relevance: VaultRelevance = Field(
        default="medium",
        description="Used by USP A scaffolder to pick the top-3 proofs at apply-time.",
    )


class Vault(_VaultBase):
    """A user's full narrated portfolio."""

    user_login: str = Field(min_length=1, max_length=120)
    user_name: str | None = None
    user_url: HttpUrl
    bio: str | None = None
    total_stars: int = Field(ge=0)
    languages_top: list[str] = Field(default_factory=list)
    entries: list[VaultEntry] = Field(default_factory=list)
    generated_at: datetime
    narration_source: Literal["llm", "fallback"] = Field(
        default="fallback",
        description="Whether the narratives came from the LLM or the deterministic templater.",
    )
