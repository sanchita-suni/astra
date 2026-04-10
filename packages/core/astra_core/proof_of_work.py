"""Extract a user's proof-of-work signal from GitHub.

This is the foundation for two USPs:
- **USP D (Vault)**: each `RepoSummary` is later narrated by `vault_crew` into a
  one-pager portfolio.
- **Trust Score**: stargazer counts, language breadth, and commit recency feed
  the weighted score in `astra_core.trust_score`.

Network-free at this layer — pass in a `GitHubClient` so callers can mock it.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from astra_github_client import GitHubClient, RepoSummary, UserSummary


class ProofOfWork(BaseModel):
    """A snapshot of what a user has actually shipped."""

    user: UserSummary
    repos: list[RepoSummary] = Field(default_factory=list)
    languages_top: list[tuple[str, int]] = Field(
        default_factory=list,
        description="Top languages by repo count, descending.",
    )
    total_stars: int = 0
    most_recent_push_at: datetime | None = None
    days_since_last_push: int | None = None


def build_proof_of_work(client: GitHubClient, login: str, *, repo_limit: int = 30) -> ProofOfWork:
    """Pull a user's profile + recent repos and aggregate into a ProofOfWork.

    Pure aggregation — no LLM, no async, no DB. Fully unit-testable with a
    fake `GitHubClient`.
    """
    user = client.get_user(login)
    repos = client.list_user_repos(login, limit=repo_limit)

    lang_counts: Counter[str] = Counter()
    for r in repos:
        if r.language:
            lang_counts[r.language] += 1

    total_stars = sum(r.stargazers_count for r in repos)

    pushed_dates = [r.pushed_at for r in repos if r.pushed_at is not None]
    most_recent = max(pushed_dates) if pushed_dates else None
    days_since = None
    if most_recent is not None:
        delta = datetime.now(timezone.utc) - most_recent
        days_since = max(0, delta.days)

    return ProofOfWork(
        user=user,
        repos=repos,
        languages_top=lang_counts.most_common(10),
        total_stars=total_stars,
        most_recent_push_at=most_recent,
        days_since_last_push=days_since,
    )
