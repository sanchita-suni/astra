"""CRUD for the `users` table.

Same JSONB-first philosophy as `repository.py`: scalar columns for things we
filter/index on, JSONB for nested data (questionnaire, resume).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from astra_api.db.models import UserRow
from astra_schemas import QuestionnaireResponse, ResumeSkills, UserProfile


async def upsert_user(
    session: AsyncSession,
    *,
    github_login: str,
    github_name: str | None = None,
    github_avatar_url: str | None = None,
    email: str | None = None,
) -> UserRow:
    """Insert or update a user on GitHub OAuth callback."""
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(UserRow)
        .values(
            user_id=str(uuid.uuid4()),
            github_login=github_login,
            github_name=github_name,
            github_avatar_url=github_avatar_url,
            email=email,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[UserRow.github_login],
            set_={
                "github_name": github_name,
                "github_avatar_url": github_avatar_url,
                "email": email,
                "updated_at": now,
            },
        )
        .returning(UserRow)
    )
    result = await session.execute(stmt)
    row = result.scalar_one()
    await session.commit()
    return row


async def get_user_by_login(session: AsyncSession, github_login: str) -> UserProfile | None:
    stmt = select(UserRow).where(UserRow.github_login == github_login)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return _to_profile(row) if row else None


async def get_user_by_id(session: AsyncSession, user_id: str) -> UserProfile | None:
    stmt = select(UserRow).where(UserRow.user_id == user_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return _to_profile(row) if row else None


async def update_questionnaire(
    session: AsyncSession, user_id: str, q: QuestionnaireResponse
) -> UserRow:
    stmt = select(UserRow).where(UserRow.user_id == user_id)
    row = (await session.execute(stmt)).scalar_one()
    row.questionnaire = json.loads(q.model_dump_json())
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return row


async def update_resume(
    session: AsyncSession,
    user_id: str,
    resume: ResumeSkills,
    filename: str | None = None,
) -> UserRow:
    stmt = select(UserRow).where(UserRow.user_id == user_id)
    row = (await session.execute(stmt)).scalar_one()
    row.resume = json.loads(resume.model_dump_json())
    row.resume_filename = filename
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return row


def _to_profile(row: UserRow) -> UserProfile:
    return UserProfile(
        user_id=row.user_id,
        github_login=row.github_login,
        github_name=row.github_name,
        github_avatar_url=row.github_avatar_url,
        email=row.email,
        questionnaire=(
            QuestionnaireResponse.model_validate(row.questionnaire)
            if row.questionnaire
            else None
        ),
        resume=(
            ResumeSkills.model_validate(row.resume) if row.resume else None
        ),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
