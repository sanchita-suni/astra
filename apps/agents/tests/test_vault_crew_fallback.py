"""vault_crew fallback tests."""

from __future__ import annotations

from datetime import datetime, timezone

from astra_agents.crews.vault_crew import build_vault
from astra_core import ProofOfWork
from astra_github_client import RepoSummary, UserSummary
from astra_schemas import Vault, VaultEntry


def _user_with_repos(n_repos: int = 3) -> ProofOfWork:
    repos = [
        RepoSummary(
            full_name=f"alice/proj-{i}",
            name=f"proj-{i}",
            description=f"Project {i} description.",
            language="Python" if i % 2 == 0 else "TypeScript",
            stargazers_count=10 + i,
            html_url=f"https://github.com/alice/proj-{i}",
            topics=["ml", "computer-vision"] if i == 0 else [],
            pushed_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        for i in range(n_repos)
    ]
    return ProofOfWork(
        user=UserSummary(
            login="alice",
            name="Alice Engineer",
            bio="Builds ML things",
            public_repos=n_repos,
            followers=15,
            html_url="https://github.com/alice",
        ),
        repos=repos,
        languages_top=[("Python", 2), ("TypeScript", 1)],
        total_stars=sum(r.stargazers_count for r in repos),
        days_since_last_push=2,
    )


def test_vault_returns_vault_with_one_entry_per_repo() -> None:
    pow_ = _user_with_repos(3)
    vault = build_vault(pow_, use_llm=False)
    assert isinstance(vault, Vault)
    assert vault.user_login == "alice"
    assert vault.user_name == "Alice Engineer"
    assert len(vault.entries) == 3
    assert vault.narration_source == "fallback"


def test_vault_caps_entries_at_max() -> None:
    pow_ = _user_with_repos(20)
    vault = build_vault(pow_, use_llm=False, max_entries=5)
    assert len(vault.entries) == 5


def test_vault_entries_sorted_by_stars_desc() -> None:
    pow_ = _user_with_repos(4)
    vault = build_vault(pow_, use_llm=False)
    star_counts = [e.stars for e in vault.entries]
    assert star_counts == sorted(star_counts, reverse=True)


def test_vault_fallback_narrative_uses_repo_metadata() -> None:
    pow_ = _user_with_repos(1)
    vault = build_vault(pow_, use_llm=False)
    entry = vault.entries[0]
    assert entry.narrative
    # Description should appear; language should appear; stars should appear
    assert "proj-0" in entry.narrative
    assert "Python" in entry.narrative
    assert "10" in entry.narrative  # 10 + 0 stars


def test_vault_entry_relevance_buckets() -> None:
    pow_ = _user_with_repos(3)
    vault = build_vault(pow_, use_llm=False)
    # The first repo has topics so it should be at least medium
    topical = next(e for e in vault.entries if e.topics)
    assert topical.relevance in ("high", "medium")


def test_vault_with_no_repos_returns_empty_entries() -> None:
    pow_ = ProofOfWork(
        user=UserSummary(login="lonely", html_url="https://github.com/lonely"),
        repos=[],
        languages_top=[],
        total_stars=0,
        days_since_last_push=None,
    )
    vault = build_vault(pow_, use_llm=False)
    assert isinstance(vault, Vault)
    assert vault.entries == []
    assert vault.user_login == "lonely"


def test_vault_entries_validate_against_schema() -> None:
    """Belt-and-suspenders: every entry must round-trip through VaultEntry."""
    pow_ = _user_with_repos(3)
    vault = build_vault(pow_, use_llm=False)
    for entry in vault.entries:
        VaultEntry.model_validate(entry.model_dump(mode="json"))
