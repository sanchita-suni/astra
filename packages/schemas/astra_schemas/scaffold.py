"""Bridge-to-Build (USP A) — scaffolder result schema.

When a user commits to a hackathon, `builder_crew` picks one of the four
hand-curated starter templates, rewrites its `BRIEF.md` with the opportunity's
specific requirements + a Day-1 task list, and (optionally) creates a real
GitHub repo. The shape returned to the API consumer is `ScaffoldResult`.

`dry_run=True` means the agent ran end-to-end but did NOT touch GitHub —
useful for tests, demo loops without a token, and previews from the frontend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

ScaffoldTemplate = Literal[
    "python-ml",
    "nextjs-fullstack",
    "fastapi-react",
    "generic-python",
]


class _ScaffoldBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class ScaffoldedFile(_ScaffoldBase):
    """A single file the scaffolder produced (or would have produced)."""

    path: str = Field(min_length=1, max_length=300, description="Repo-relative path.")
    bytes: int = Field(ge=0)


class ScaffoldResult(_ScaffoldBase):
    """The full output of `POST /opportunities/{id}/scaffold`."""

    opportunity_id: str = Field(min_length=1)
    template: ScaffoldTemplate
    repo_name: str = Field(min_length=1, max_length=120)
    repo_url: HttpUrl | None = Field(
        default=None,
        description="Live GitHub URL when `dry_run=False`; null on dry runs.",
    )
    brief_markdown: str = Field(min_length=1)
    files: list[ScaffoldedFile] = Field(default_factory=list)
    created_at: datetime
    dry_run: bool
    brief_source: Literal["llm", "fallback"] = Field(
        default="fallback",
        description="Whether the BRIEF.md prose came from the LLM or the templater.",
    )
