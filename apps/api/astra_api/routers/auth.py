"""GitHub OAuth authentication.

Flow:
1. Frontend links to `GET /auth/github` → redirects to GitHub
2. GitHub redirects back to `GET /auth/github/callback` with a `code`
3. We exchange the code for a token, fetch the user, upsert in DB, set a JWT cookie
4. Frontend calls `GET /auth/me` to get the current user from the cookie
5. `POST /auth/logout` clears the cookie

No NextAuth. No frontend auth library. The JWT lives in an httpOnly cookie
so it's automatically sent with every request.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from astra_api.db import user_repository
from astra_api.deps import get_session
from astra_api.settings import settings
from astra_schemas import UserProfile

logger = logging.getLogger("astra.api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

COOKIE_NAME = "astra_session"
JWT_ALGORITHM = "HS256"


def _create_jwt(user_id: str, github_login: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=settings.session_expire_days)
    return jwt.encode(
        {"user_id": user_id, "github_login": github_login, "exp": exp},
        settings.session_secret,
        algorithm=JWT_ALGORITHM,
    )


def _decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.session_secret, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/github")
async def github_login(request: Request) -> Response:
    """Redirect the browser to GitHub's OAuth authorize page."""
    if not settings.github_client_id:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env",
        )
    url = (
        f"{GITHUB_AUTHORIZE_URL}"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_callback_url}"
        f"&scope=read:user,user:email"
    )
    return Response(status_code=302, headers={"Location": url})


@router.get("/github/callback")
async def github_callback(
    code: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Exchange the GitHub code for a token, upsert the user, set the session cookie."""
    # Exchange code for access token
    token_resp = httpx.post(
        GITHUB_TOKEN_URL,
        data={
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"GitHub OAuth failed: {token_data}")

    # Fetch user profile
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    user_resp = httpx.get(GITHUB_USER_URL, headers=headers, timeout=10)
    gh_user = user_resp.json()

    # Fetch primary email
    email = gh_user.get("email")
    if not email:
        try:
            emails_resp = httpx.get(GITHUB_EMAILS_URL, headers=headers, timeout=10)
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            email = primary["email"] if primary else None
        except Exception:
            pass

    # Upsert user in DB
    row = await user_repository.upsert_user(
        session,
        github_login=gh_user["login"],
        github_name=gh_user.get("name"),
        github_avatar_url=gh_user.get("avatar_url"),
        email=email,
    )

    # Create JWT and set cookie
    token = _create_jwt(row.user_id, row.github_login)

    # Check if user needs onboarding (no questionnaire yet)
    redirect_url = settings.frontend_url
    if row.questionnaire is None:
        redirect_url = f"{settings.frontend_url}/onboarding"

    response = Response(status_code=302, headers={"Location": redirect_url})
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_expire_days * 86400,
        path="/",
    )

    # Send welcome email with top opportunities (fire-and-forget)
    if email:
        import asyncio as _aio
        from astra_api.db import repository
        from astra_api.email import build_welcome_email, send_email_async
        from astra_api.db.user_repository import _to_profile

        async def _send_welcome():
            try:
                user_profile = _to_profile(row)
                opps = await repository.list_opportunities(session, limit=10)
                html = build_welcome_email(user_profile, opps[:10])
                await send_email_async(email, "Welcome to Astra — Your Top Hackathons", html)
            except Exception as exc:
                logger.warning("Welcome email failed: %s", exc)

        _aio.ensure_future(_send_welcome())

    return response


@router.get("/me", response_model=UserProfile | None)
async def get_me(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserProfile | None:
    """Return the current authenticated user, or null if not logged in."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    claims = _decode_jwt(token)
    if not claims:
        return None
    try:
        return await user_repository.get_user_by_id(session, claims["user_id"])
    except Exception:
        return None


@router.post("/logout")
async def logout() -> Response:
    response = Response(status_code=200, content='{"ok": true}', media_type="application/json")
    response.delete_cookie(COOKIE_NAME, path="/")
    return response
