"""Weighted trust score from a user's proof-of-work.

Returns 0-100. The breakdown is exposed so the analyst_crew can write a
plain-English explanation of *why* a score is what it is — that's much more
valuable than a single magic number.

Weights are deliberately tunable constants at the top of the file so they can
be adjusted by inspection rather than chasing magic numbers through a YAML.

The `user_trust_score` field on `MatchAnalysis` clamps to int 0..100, so we
return ints here too.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from astra_core.proof_of_work import ProofOfWork

# ---------------------------------------------------------------------------
# Tunable weights — sum should be 1.0. Adjust based on signal quality.
# ---------------------------------------------------------------------------
WEIGHT_REPO_COUNT = 0.25
WEIGHT_LANGUAGE_BREADTH = 0.20
WEIGHT_STARS = 0.20
WEIGHT_RECENCY = 0.25
WEIGHT_FOLLOWERS = 0.10

# Saturation points — beyond these we don't reward more.
REPO_COUNT_SATURATION = 20
LANGUAGE_BREADTH_SATURATION = 5
STARS_SATURATION = 100
FOLLOWERS_SATURATION = 100
RECENCY_DAYS_FRESH = 14    # 100% recency below this
RECENCY_DAYS_STALE = 180   # 0% recency at/above this


class TrustScoreBreakdown(BaseModel):
    """Itemized contribution from each signal — sum equals the final score."""

    repo_count_score: float = Field(ge=0)
    language_breadth_score: float = Field(ge=0)
    stars_score: float = Field(ge=0)
    recency_score: float = Field(ge=0)
    followers_score: float = Field(ge=0)
    total: int = Field(ge=0, le=100)


def compute_trust_score(pow_: ProofOfWork) -> TrustScoreBreakdown:
    repo_factor = min(len(pow_.repos), REPO_COUNT_SATURATION) / REPO_COUNT_SATURATION
    lang_factor = (
        min(len(pow_.languages_top), LANGUAGE_BREADTH_SATURATION) / LANGUAGE_BREADTH_SATURATION
    )
    stars_factor = min(pow_.total_stars, STARS_SATURATION) / STARS_SATURATION
    followers_factor = min(pow_.user.followers, FOLLOWERS_SATURATION) / FOLLOWERS_SATURATION

    if pow_.days_since_last_push is None:
        recency_factor = 0.0
    elif pow_.days_since_last_push <= RECENCY_DAYS_FRESH:
        recency_factor = 1.0
    elif pow_.days_since_last_push >= RECENCY_DAYS_STALE:
        recency_factor = 0.0
    else:
        span = RECENCY_DAYS_STALE - RECENCY_DAYS_FRESH
        offset = pow_.days_since_last_push - RECENCY_DAYS_FRESH
        recency_factor = max(0.0, 1.0 - offset / span)

    repo_score = repo_factor * WEIGHT_REPO_COUNT * 100
    lang_score = lang_factor * WEIGHT_LANGUAGE_BREADTH * 100
    stars_score = stars_factor * WEIGHT_STARS * 100
    recency_score = recency_factor * WEIGHT_RECENCY * 100
    followers_score = followers_factor * WEIGHT_FOLLOWERS * 100

    total = round(repo_score + lang_score + stars_score + recency_score + followers_score)
    total = max(0, min(100, total))

    return TrustScoreBreakdown(
        repo_count_score=round(repo_score, 2),
        language_breadth_score=round(lang_score, 2),
        stars_score=round(stars_score, 2),
        recency_score=round(recency_score, 2),
        followers_score=round(followers_score, 2),
        total=total,
    )
