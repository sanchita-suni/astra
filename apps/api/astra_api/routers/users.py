"""User routes — vault (USP D), profile, resume upload, questionnaire, feed.

These endpoints power the personalization layer. Most require auth
(`require_current_user`), except the vault which works for any GitHub login.
"""

from __future__ import annotations

import asyncio
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from astra_agents.crews.vault_crew import build_vault
from astra_api.db import repository, user_repository
from astra_api.deps import get_current_user, get_session, require_current_user
from astra_core import build_proof_of_work
from astra_core.feed_ranker import rank_opportunities
from astra_core.resume_parser import extract_skills_from_text
from astra_github_client import GitHubClient
from astra_schemas import (
    Opportunity,
    QuestionnaireResponse,
    ResumeSkills,
    UserProfile,
    Vault,
)

logger = logging.getLogger("astra.api.users")

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Vault (USP D) — no auth required
# ---------------------------------------------------------------------------


def _build_vault_sync(login: str, *, use_llm: bool) -> Vault:
    client = GitHubClient()
    pow_ = build_proof_of_work(client, login)
    return build_vault(pow_, use_llm=use_llm)


@router.get("/{login}/vault", response_model=Vault)
async def get_user_vault(
    login: str,
    use_llm: bool = Query(default=True),
) -> Vault:
    """Return the auto-narrated Proof-of-Work Vault for a GitHub user."""
    try:
        vault = await asyncio.to_thread(_build_vault_sync, login, use_llm=use_llm)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except Exception as exc:
        logger.exception("vault build failed for %r", login)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return vault


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get("/me/profile", response_model=UserProfile)
async def get_my_profile(
    user: UserProfile = Depends(require_current_user),
) -> UserProfile:
    return user


@router.get("/{login}/profile", response_model=UserProfile)
async def get_user_profile(
    login: str,
    session: AsyncSession = Depends(get_session),
) -> UserProfile:
    profile = await user_repository.get_user_by_login(session, login)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"User {login!r} not found")
    return profile


# ---------------------------------------------------------------------------
# Onboarding questionnaire
# ---------------------------------------------------------------------------


@router.put("/me/questionnaire", response_model=UserProfile)
async def update_questionnaire(
    body: QuestionnaireResponse,
    user: UserProfile = Depends(require_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserProfile:
    """Save or update the onboarding questionnaire answers."""
    await user_repository.update_questionnaire(session, user.user_id, body)
    updated = await user_repository.get_user_by_id(session, user.user_id)
    if updated is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR)
    return updated


# ---------------------------------------------------------------------------
# Resume upload
# ---------------------------------------------------------------------------


@router.post("/me/resume", response_model=ResumeSkills)
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file"),
    user: UserProfile = Depends(require_current_user),
    session: AsyncSession = Depends(get_session),
) -> ResumeSkills:
    """Upload a PDF resume. Extracts skills via keyword matching."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF files are accepted")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too large (max 5MB)")

    # Extract text from PDF
    def _extract() -> str:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        text_parts: list[str] = []
        for page in reader.pages[:20]:  # cap at 20 pages
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)

    text = await asyncio.to_thread(_extract)
    if not text.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not extract text from PDF. Is it a scanned image?",
        )

    # Extract skills
    resume = extract_skills_from_text(text)
    await user_repository.update_resume(
        session, user.user_id, resume, filename=file.filename
    )
    return resume


# ---------------------------------------------------------------------------
# Personalized feed
# ---------------------------------------------------------------------------


@router.get("/me/feed", response_model=list[dict])
async def get_personalized_feed(
    user: UserProfile = Depends(require_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return opportunities ranked by match score for the authenticated user."""
    # Get all opportunities from DB
    try:
        opportunities = await repository.list_opportunities(session, limit=100)
    except Exception:
        opportunities = []

    if not opportunities:
        return []

    # Collect user's GitHub languages (if we can fetch them quickly)
    github_languages: list[str] = []
    if user.resume and user.resume.skills:
        github_languages = list(user.resume.skills)

    ranked = rank_opportunities(
        opportunities,
        github_languages=github_languages,
        resume=user.resume,
        questionnaire=user.questionnaire,
    )

    return [
        {
            "opportunity": opp.model_dump(mode="json"),
            "match_score": score,
        }
        for opp, score in ranked
    ]
