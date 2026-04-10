"""Intermediate types used between scrapers and the canonical Opportunity contract.

A spider only knows things it can read off a page: title, organization,
deadline, mode, apply link, raw requirements. It does NOT know things
that come from the analyst/roadmap/deadman pipelines (fit %, trust score,
recommended start date, bridge roadmap, etc.).

So scrapers produce a `ScrapedOpportunity` — a strictly typed *subset* of the
full Opportunity Digest — and a `to_stub_opportunity()` bridge fills in safe
placeholder values for the analyst-driven sections. Day 3 crews then overwrite
those placeholders with real values.

This split keeps the contract intact (the schemas package never weakens its
required fields) while letting the Day 2 ingest pipeline run end-to-end before
the Day 3 crews exist.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from astra_schemas import (
    ExecutionIntel,
    MatchAnalysis,
    Metadata,
    Opportunity,
    ReadinessEngine,
    TeammateMatchmaker,
)


class ScrapedOpportunity(BaseModel):
    """Strict subset of `Opportunity` containing only spider-knowable fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    opportunity_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=100)
    type: str = Field(default="Hackathon")  # Astra is hackathons-only for V1
    mode: str = Field(default="Remote")
    deadline: datetime
    apply_link: HttpUrl
    raw_requirements: list[str] = Field(default_factory=list)

    def to_stub_opportunity(self) -> Opportunity:
        """Lift to a full `Opportunity` with placeholder analyst-driven fields.

        Day 3 crews (analyst, roadmap, deadman) overwrite the stub fields with
        real values. Until they exist, the placeholders let the API serve the
        scraped row through the same `/opportunities/{id}` shape used by the
        Next.js frontend.
        """
        # Default safe start: 7 days before the deadline. Replaced by the
        # deadman switch on Day 3 once real velocity data exists.
        recommended_start = self.deadline - timedelta(days=7)
        if recommended_start.tzinfo is None:
            recommended_start = recommended_start.replace(tzinfo=timezone.utc)

        return Opportunity(
            opportunity_id=self.opportunity_id,
            metadata=Metadata(
                title=self.title,
                organization=self.organization,
                source=self.source,
                type=self.type,  # type: ignore[arg-type]  # validated by Literal
                mode=self.mode,  # type: ignore[arg-type]
                deadline_iso=self.deadline,
                apply_link=self.apply_link,
                raw_requirements=list(self.raw_requirements),
            ),
            match_analysis=MatchAnalysis(
                overall_fit_percentage=0,
                semantic_overlap_score=0,
                user_trust_score=0,
                ai_reasoning="(pending analyst crew)",
            ),
            execution_intel=ExecutionIntel(
                complexity_to_time_ratio="Medium",
                estimated_hours_required=20,
                recommended_start_date_iso=recommended_start,
                deadman_switch_alert="(pending deadman switch)",
            ),
            readiness_engine=ReadinessEngine(
                skill_gap_identified=[],
                bridge_roadmap=[],
            ),
            teammate_matchmaker=TeammateMatchmaker(suggested_super_team=[]),
        )
