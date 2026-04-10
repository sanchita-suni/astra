"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from astra_api.db import user_repository
from astra_api.db.session import async_session
from astra_api.settings import settings
from astra_schemas import UserProfile

COOKIE_NAME = "astra_session"
JWT_ALGORITHM = "HS256"


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserProfile | None:
    """Extract user from JWT cookie. Returns None if not authenticated."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        claims = jwt.decode(token, settings.session_secret, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    try:
        return await user_repository.get_user_by_id(session, claims["user_id"])
    except Exception:
        return None


async def require_current_user(
    user: UserProfile | None = Depends(get_current_user),
) -> UserProfile:
    """Same as get_current_user but raises 401 if not logged in."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    return user
