"""GitHub client wrapper — auth, fetch, and shape into Pydantic models.

Reads `GITHUB_TOKEN` from env. Falls back to anonymous access (rate-limited
hard) when no token is set, which is fine for local fixture testing.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime, timezone

from github import Auth, Github
from github.GithubException import GithubException, UnknownObjectException
from pydantic import BaseModel, Field


class RepoSummary(BaseModel):
    """Compact view of a GitHub repo, suitable for the Vault and Trust Score."""

    full_name: str
    name: str
    description: str | None = None
    language: str | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    pushed_at: datetime | None = None
    created_at: datetime | None = None
    html_url: str
    topics: list[str] = Field(default_factory=list)


class UserSummary(BaseModel):
    """Compact view of a GitHub user."""

    login: str
    name: str | None = None
    bio: str | None = None
    public_repos: int = 0
    followers: int = 0
    avatar_url: str | None = None
    html_url: str


class GitHubClient:
    """Centralized GitHub access. Inject into services that need git data."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token or os.getenv("GITHUB_TOKEN") or None
        auth = Auth.Token(self._token) if self._token else None
        self._gh = Github(auth=auth) if auth else Github()

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    def get_user(self, login: str) -> UserSummary:
        try:
            u = self._gh.get_user(login)
        except UnknownObjectException as exc:
            raise ValueError(f"GitHub user {login!r} not found") from exc
        return UserSummary(
            login=u.login,
            name=u.name,
            bio=u.bio,
            public_repos=u.public_repos or 0,
            followers=u.followers or 0,
            avatar_url=u.avatar_url,
            html_url=u.html_url,
        )

    # ------------------------------------------------------------------
    # Repos
    # ------------------------------------------------------------------

    def list_user_repos(self, login: str, *, limit: int = 30) -> list[RepoSummary]:
        """Return the user's most recently pushed repos, capped at `limit`."""
        try:
            user = self._gh.get_user(login)
        except UnknownObjectException as exc:
            raise ValueError(f"GitHub user {login!r} not found") from exc

        # `sort=pushed` returns most recent activity first — best signal for "what
        # is this user actually working on right now."
        repos = user.get_repos(sort="pushed", direction="desc")
        results: list[RepoSummary] = []
        for repo in repos[:limit]:
            results.append(self._summarize(repo))
        return results

    def get_repo_summary(self, full_name: str) -> RepoSummary:
        try:
            repo = self._gh.get_repo(full_name)
        except UnknownObjectException as exc:
            raise ValueError(f"GitHub repo {full_name!r} not found") from exc
        return self._summarize(repo)

    @staticmethod
    def _summarize(repo) -> RepoSummary:  # type: ignore[no-untyped-def]
        return RepoSummary(
            full_name=repo.full_name,
            name=repo.name,
            description=repo.description,
            language=repo.language,
            stargazers_count=repo.stargazers_count or 0,
            forks_count=repo.forks_count or 0,
            pushed_at=_aware(repo.pushed_at),
            created_at=_aware(repo.created_at),
            html_url=repo.html_url,
            topics=_safe_topics(repo),
        )

    # ------------------------------------------------------------------
    # Repo creation (USP A — Bridge-to-Build scaffolder)
    # ------------------------------------------------------------------

    def create_repo_for_authenticated_user(
        self,
        name: str,
        *,
        description: str = "",
        private: bool = False,
        auto_init: bool = False,
    ) -> RepoSummary:
        if not self._token:
            raise RuntimeError(
                "GitHub repo creation requires a personal access token (set GITHUB_TOKEN)."
            )
        try:
            user = self._gh.get_user()
            repo = user.create_repo(
                name=name,
                description=description,
                private=private,
                auto_init=auto_init,
            )
        except GithubException as exc:
            raise RuntimeError(f"GitHub create_repo failed: {exc.data}") from exc
        return self._summarize(repo)

    def create_file_in_repo(
        self,
        full_name: str,
        path: str,
        content: str,
        *,
        message: str = "Astra scaffold",
    ) -> None:
        """Create a single file in an existing repo (used by USP A scaffolder).

        Requires the repo to have a default branch — pass `auto_init=True` to
        `create_repo_for_authenticated_user` so the initial commit + branch
        exist before this is called.
        """
        if not self._token:
            raise RuntimeError("GitHub file creation requires a personal access token.")
        try:
            repo = self._gh.get_repo(full_name)
            repo.create_file(path, message, content)
        except GithubException as exc:
            raise RuntimeError(f"GitHub create_file failed for {path!r}: {exc.data}") from exc


def _safe_topics(repo) -> list[str]:  # type: ignore[no-untyped-def]
    """Get repo topics, swallowing rate-limit errors."""
    try:
        if hasattr(repo, "get_topics"):
            return list(repo.get_topics() or [])
    except Exception:
        pass
    return []


def _aware(dt: datetime | None) -> datetime | None:
    """Coerce naive datetimes to UTC-aware (PyGithub returns naive UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
