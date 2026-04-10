"""Opportunity routes — the contract surface every consumer hits.

Day 2: reads from Postgres, with the canonical fixture preserved as a hard
fallback for the magic ID `demo`. Writes (`POST /opportunities`) accept any
validated `Opportunity` and upsert it — that's the surface scrapers and
crews talk to so the API stays the only thing that touches the DB.

Day 4 additions:
- POST /opportunities/{id}/scaffold — USP A Bridge-to-Build scaffolder
- POST /opportunities/{id}/dry-run  — USP B Dry-Run Demo Day judge panel

`/opportunities/demo` deliberately bypasses the DB so it works even when
Postgres is offline (Day 1 acceptance contract).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from astra_agents.crews.builder_crew import scaffold_to_directory, scaffold_to_github
from astra_agents.crews.judge_crew import run_dry_run
from astra_api.db import repository
from astra_api.db.models import RegistrationRow
from astra_api.deps import get_current_user, get_session, require_current_user
from astra_api.fixtures import load_demo_opportunity
from astra_core.feed_ranker import score_opportunity, _collect_user_skills, _build_user_text
from astra_github_client import GitHubClient
from astra_schemas import (
    DryRunRequest,
    DryRunRubric,
    MatchAnalysis,
    Opportunity,
    ScaffoldResult,
    UserProfile,
)

logger = logging.getLogger("astra.api.opportunities")

router = APIRouter(prefix="/opportunities", tags=["opportunities"])

DEMO_ID = "demo"


@router.get("/{opportunity_id}", response_model=Opportunity)
async def get_opportunity(
    opportunity_id: str,
    session: AsyncSession = Depends(get_session),
    user: UserProfile | None = Depends(get_current_user),
) -> Opportunity:
    """Fetch a single opportunity by id, personalized for the logged-in user."""
    if opportunity_id == DEMO_ID:
        return load_demo_opportunity()

    try:
        opp = await repository.get_opportunity_by_id(session, opportunity_id)
    except Exception as exc:
        logger.warning("get_opportunity_by_id failed for %r: %s", opportunity_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    if opp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity {opportunity_id!r} not found",
        )

    # Personalize for the logged-in user
    if user:
        result = _personalize([opp], user)
        if result:
            return result[0]
    return opp


# Cache GitHub signal per user — avoids hitting GitHub API on every page load.
# TTL: lives for the process lifetime. Cleared on restart.
_github_signal_cache: dict[str, list[str]] = {}


def _get_github_signal(login: str) -> list[str]:
    """Fetch and cache the user's GitHub skill signal."""
    if login in _github_signal_cache:
        return _github_signal_cache[login]

    try:
        from astra_agents.crews.analyst_crew import _user_signal
        from astra_core import build_proof_of_work

        import os
        token = os.environ.get("GITHUB_TOKEN", "")
        gh_client = GitHubClient(token=token if token else None)
        pow_ = build_proof_of_work(gh_client, login)
        signal = list(_user_signal(pow_))
        _github_signal_cache[login] = signal
        logger.info("Cached GitHub signal for %s: %d tokens", login, len(signal))
        return signal
    except Exception as exc:
        logger.debug("GitHub fetch failed for %s: %s", login, exc)
        return []


# Cache the full ProofOfWork per user for enrichment
_pow_cache: dict[str, object] = {}


def _get_user_pow(login: str):
    """Fetch and cache the user's ProofOfWork."""
    if login in _pow_cache:
        return _pow_cache[login]
    try:
        import os
        from astra_core import build_proof_of_work
        token = os.environ.get("GITHUB_TOKEN", "")
        gh_client = GitHubClient(token=token if token else None)
        pow_ = build_proof_of_work(gh_client, login)
        _pow_cache[login] = pow_
        return pow_
    except Exception as exc:
        logger.debug("GitHub fetch failed for %s: %s", login, exc)
        return None


def _personalize(opps: list[Opportunity], user: UserProfile | None) -> list[Opportunity]:
    """Fully enrich opportunities for the logged-in user.

    Computes: fit score, semantic overlap, trust score, skill gap, roadmap,
    deadman switch, AI reasoning (fallback). Sort by fit descending.
    """
    if not user:
        opps.sort(key=lambda o: o.metadata.deadline_iso)
        return opps

    from astra_agents.crews.analyst_crew import enrich_opportunity
    from astra_agents.crews.roadmap_crew import attach_roadmap_to_opportunity
    from datetime import datetime, timezone

    pow_ = _get_user_pow(user.github_login)
    if pow_ is None:
        # Can't enrich without GitHub data — return as-is sorted by deadline
        opps.sort(key=lambda o: o.metadata.deadline_iso)
        return opps

    now = datetime.now(timezone.utc)
    scored: list[tuple[Opportunity, float]] = []

    for opp in opps:
        try:
            enriched = enrich_opportunity(opp, pow_, use_llm=False, now=now)
            final = attach_roadmap_to_opportunity(enriched, use_llm=False)
            scored.append((final, final.match_analysis.overall_fit_percentage))
        except Exception:
            scored.append((opp, 0))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [opp for opp, _ in scored]


@router.get("", response_model=list[Opportunity])
async def list_opportunities(
    session: AsyncSession = Depends(get_session),
    user: UserProfile | None = Depends(get_current_user),
) -> list[Opportunity]:
    """List opportunities, personalized for the logged-in user.

    - Logged in: re-scores every opportunity against user's resume +
      questionnaire + GitHub skills, sorts by fit descending.
    - Anonymous: sorts by deadline (soonest first).
    """
    try:
        rows = await repository.list_opportunities(session, limit=200)
    except Exception as exc:
        logger.warning("list_opportunities DB error, falling back to fixture: %s", exc)
        return [load_demo_opportunity()]

    if not rows:
        return [load_demo_opportunity()]

    return _personalize(rows, user)


@router.post(
    "",
    response_model=Opportunity,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_opportunity(
    opp: Opportunity,
    session: AsyncSession = Depends(get_session),
) -> Opportunity:
    """Idempotent upsert — scrapers and crews POST validated digests here.

    The request body is validated through the same `Opportunity` model the
    rest of the system uses, so a malformed scrape is rejected at the
    boundary instead of poisoning the DB.
    """
    try:
        await repository.upsert_opportunity(session, opp)
    except Exception as exc:
        logger.error("upsert_opportunity failed for %r: %s", opp.opportunity_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return opp


# ---------------------------------------------------------------------------
# USP A — Bridge-to-Build scaffolder
# ---------------------------------------------------------------------------


async def _get_opp(
    opportunity_id: str, session: AsyncSession
) -> Opportunity:
    if opportunity_id == DEMO_ID:
        return load_demo_opportunity()
    try:
        opp = await repository.get_opportunity_by_id(session, opportunity_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "DB unavailable") from exc
    if opp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Opportunity {opportunity_id!r} not found")
    return opp


@router.post(
    "/{opportunity_id}/scaffold",
    response_model=ScaffoldResult,
    status_code=status.HTTP_201_CREATED,
    tags=["scaffold"],
)
async def scaffold_opportunity(
    opportunity_id: str,
    session: AsyncSession = Depends(get_session),
    dry_run: bool = Query(
        default=True,
        description="If true, generate the brief + file list but do NOT "
        "create a GitHub repo. Set to false to actually create the repo.",
    ),
    repo_name: str | None = Query(default=None),
    use_llm: bool = Query(default=True),
) -> ScaffoldResult:
    """USP A — pick the right starter template, write a BRIEF.md, and
    (optionally) create a GitHub repo under the authenticated user."""
    opp = await _get_opp(opportunity_id, session)

    if dry_run:
        import tempfile
        from pathlib import Path

        def _do() -> ScaffoldResult:
            with tempfile.TemporaryDirectory(prefix="astra-") as tmp:
                return scaffold_to_directory(
                    opp, Path(tmp), use_llm=use_llm, repo_name=repo_name
                )

        return await asyncio.to_thread(_do)
    else:
        def _do_github() -> ScaffoldResult:
            return scaffold_to_github(
                opp,
                github=GitHubClient(),
                repo_name=repo_name,
                use_llm=use_llm,
            )

        try:
            return await asyncio.to_thread(_do_github)
        except RuntimeError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ---------------------------------------------------------------------------
# USP B — Dry-Run Demo Day judge panel
# ---------------------------------------------------------------------------


@router.post(
    "/{opportunity_id}/dry-run",
    response_model=DryRunRubric,
    tags=["rehearsal"],
)
async def dry_run_opportunity(
    opportunity_id: str,
    body: DryRunRequest,
    session: AsyncSession = Depends(get_session),
    use_llm: bool = Query(default=True),
) -> DryRunRubric:
    """USP B — submit a project pitch and get a 3-judge rubric back.

    Single-shot: all three judges score the pitch in one call and return
    numeric rubrics + feedback. No multi-turn; the plan reserves that for V2.
    """
    opp = await _get_opp(opportunity_id, session)
    repo_url = str(body.repo_url) if body.repo_url else None

    def _do() -> DryRunRubric:
        return run_dry_run(opp, body.pitch, repo_url=repo_url, use_llm=use_llm)

    return await asyncio.to_thread(_do)


# ---------------------------------------------------------------------------
# Registration tracking
# ---------------------------------------------------------------------------


@router.post("/{opportunity_id}/register", tags=["registrations"])
async def register_for_opportunity(
    opportunity_id: str,
    user: UserProfile = Depends(require_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Register the current user for a hackathon. Sends bridge roadmap email."""
    opp = await _get_opp(opportunity_id, session)
    stmt = (
        pg_insert(RegistrationRow)
        .values(user_id=user.user_id, opportunity_id=opportunity_id)
        .on_conflict_do_nothing(index_elements=["user_id", "opportunity_id"])
    )
    await session.execute(stmt)
    await session.commit()

    # Send registration email with bridge roadmap (fire-and-forget)
    if user.email:
        from astra_api.email import build_registration_email, send_email_async
        asyncio.ensure_future(
            send_email_async(
                user.email,
                f"Registered: {opp.metadata.title} — Your Bridge Roadmap",
                build_registration_email(user, opp),
            )
        )

    return {"registered": True, "opportunity_id": opportunity_id}


@router.delete("/{opportunity_id}/register", tags=["registrations"])
async def unregister_from_opportunity(
    opportunity_id: str,
    user: UserProfile = Depends(require_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Unregister the current user from a hackathon."""
    stmt = delete(RegistrationRow).where(
        RegistrationRow.user_id == user.user_id,
        RegistrationRow.opportunity_id == opportunity_id,
    )
    await session.execute(stmt)
    await session.commit()
    return {"registered": False, "opportunity_id": opportunity_id}


@router.get("/me/registered", tags=["registrations"])
async def list_my_registrations(
    user: UserProfile = Depends(require_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Opportunity]:
    """List all hackathons the current user has registered for."""
    stmt = select(RegistrationRow.opportunity_id).where(
        RegistrationRow.user_id == user.user_id
    )
    result = await session.execute(stmt)
    opp_ids = [row[0] for row in result.all()]
    if not opp_ids:
        return []
    opps = []
    for oid in opp_ids:
        try:
            opp = await repository.get_opportunity_by_id(session, oid)
            if opp:
                opps.append(opp)
        except Exception:
            pass
    return opps
