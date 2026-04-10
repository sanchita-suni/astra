"""Unit tests for the trust score + deadman switch math.

Both modules are pure-Python and deterministic — they should not require any
network, DB, or LLM. These tests double as the executable spec for the math.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from astra_core.deadman import DeadmanInputs, compute_deadman_alert
from astra_core.proof_of_work import ProofOfWork
from astra_core.trust_score import compute_trust_score
from astra_github_client import RepoSummary, UserSummary


# ---------------------------------------------------------------------------
# Trust score
# ---------------------------------------------------------------------------


def _make_pow(
    *,
    repos: int,
    languages: int,
    stars: int,
    followers: int,
    days_since_push: int | None,
) -> ProofOfWork:
    user = UserSummary(login="alice", followers=followers, public_repos=repos, html_url="https://github.com/alice")
    repo_list = [
        RepoSummary(
            full_name=f"alice/repo{i}",
            name=f"repo{i}",
            language=f"lang{i % max(1, languages)}",
            stargazers_count=(stars // repos) if repos else 0,
            html_url=f"https://github.com/alice/repo{i}",
        )
        for i in range(repos)
    ]
    pow_ = ProofOfWork(
        user=user,
        repos=repo_list,
        languages_top=[(f"lang{i}", 1) for i in range(languages)],
        total_stars=stars,
        most_recent_push_at=None,
        days_since_last_push=days_since_push,
    )
    return pow_


def test_trust_score_zero_signal_returns_zero() -> None:
    pow_ = _make_pow(repos=0, languages=0, stars=0, followers=0, days_since_push=None)
    result = compute_trust_score(pow_)
    assert result.total == 0


def test_trust_score_perfect_signal_returns_100() -> None:
    pow_ = _make_pow(
        repos=20,
        languages=5,
        stars=100,
        followers=100,
        days_since_push=0,
    )
    result = compute_trust_score(pow_)
    assert result.total == 100


def test_trust_score_clamped_above_100() -> None:
    pow_ = _make_pow(
        repos=200,        # past saturation
        languages=50,     # past saturation
        stars=10_000,     # past saturation
        followers=10_000, # past saturation
        days_since_push=0,
    )
    result = compute_trust_score(pow_)
    assert result.total == 100


def test_trust_score_recency_decay() -> None:
    fresh = _make_pow(repos=5, languages=2, stars=10, followers=5, days_since_push=7)
    middle = _make_pow(repos=5, languages=2, stars=10, followers=5, days_since_push=90)
    stale = _make_pow(repos=5, languages=2, stars=10, followers=5, days_since_push=365)
    fresh_score = compute_trust_score(fresh)
    middle_score = compute_trust_score(middle)
    stale_score = compute_trust_score(stale)
    assert fresh_score.total > middle_score.total > stale_score.total


# ---------------------------------------------------------------------------
# Deadman switch
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)


def test_deadman_inactive_when_far_away() -> None:
    deadline = NOW + timedelta(days=60)
    inputs = DeadmanInputs(
        deadline=deadline,
        estimated_hours_required=40,
        user_avg_hours_per_day=2.0,
        velocity_multiplier=1.0,
        now=NOW,
    )
    result = compute_deadman_alert(inputs)
    # 40h / 2h per day * 1.2 buffer = 24 days needed -> recommended start ~36 days from now
    assert not result.is_alert_active
    assert result.days_buffer > 0
    assert "safely start" in result.alert_text


def test_deadman_active_when_inside_safe_window() -> None:
    deadline = NOW + timedelta(days=15)
    inputs = DeadmanInputs(
        deadline=deadline,
        estimated_hours_required=40,
        user_avg_hours_per_day=2.0,
        velocity_multiplier=1.0,
        now=NOW,
    )
    result = compute_deadman_alert(inputs)
    # 40h / 2 * 1.2 = 24 days needed; deadline is 15 days out -> behind by 9 days
    assert result.is_alert_active
    assert result.days_buffer < 0
    assert "past the safe start point" in result.alert_text


def test_deadman_slower_velocity_fires_earlier() -> None:
    deadline = NOW + timedelta(days=30)
    fast = DeadmanInputs(
        deadline=deadline,
        estimated_hours_required=40,
        user_avg_hours_per_day=2.0,
        velocity_multiplier=2.0,
        now=NOW,
    )
    slow = DeadmanInputs(
        deadline=deadline,
        estimated_hours_required=40,
        user_avg_hours_per_day=2.0,
        velocity_multiplier=0.5,
        now=NOW,
    )
    fast_result = compute_deadman_alert(fast)
    slow_result = compute_deadman_alert(slow)
    # Slower velocity → less buffer (alert may already be active)
    assert slow_result.days_buffer < fast_result.days_buffer
