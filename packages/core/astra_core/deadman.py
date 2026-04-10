"""The Deadman Switch — *personal-velocity-calibrated* deadline math.

Most platforms show generic countdowns. Astra calibrates to *your* commit
velocity: if you're slow, the alert fires earlier. The result is a single
human-readable string injected into `ExecutionIntel.deadman_switch_alert`.

Pure-Python; no I/O. Inputs are aggregated upstream from the user's GitHub
data + the opportunity's deadline. Caller decides when to trigger the alert
(the worker on Day 4).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field


class DeadmanInputs(BaseModel):
    """Everything the deadman switch needs to make a decision."""

    deadline: datetime = Field(description="Opportunity deadline (timezone-aware).")
    estimated_hours_required: int = Field(ge=1)
    user_avg_hours_per_day: float = Field(
        gt=0,
        description="User's typical productive hours/day on side projects (computed from commit cadence).",
    )
    velocity_multiplier: float = Field(
        default=1.0,
        gt=0,
        description="<1.0 means user is slower than estimate; >1.0 faster.",
    )
    now: datetime | None = Field(default=None, description="Override for tests; defaults to UTC now.")


class DeadmanResult(BaseModel):
    recommended_start: datetime
    days_buffer: int = Field(
        description=(
            "Days between recommended start and now. Negative means alert should "
            "have already fired (you're behind)."
        )
    )
    alert_text: str
    is_alert_active: bool


def compute_deadman_alert(inputs: DeadmanInputs) -> DeadmanResult:
    now = inputs.now or datetime.now(timezone.utc)
    if inputs.deadline.tzinfo is None:
        deadline = inputs.deadline.replace(tzinfo=timezone.utc)
    else:
        deadline = inputs.deadline

    # Adjust the time budget by velocity. If the user is half-speed, double the time.
    effective_hours = inputs.estimated_hours_required / max(0.1, inputs.velocity_multiplier)
    effective_days = effective_hours / max(0.1, inputs.user_avg_hours_per_day)
    # Add a 20% safety buffer for unknown unknowns
    buffered_days = effective_days * 1.2

    recommended_start = deadline - timedelta(days=buffered_days)
    days_buffer = (recommended_start - now).days

    if days_buffer < 0:
        alert_text = (
            f"You are {abs(days_buffer)} day(s) past the safe start point for this "
            f"opportunity (deadline {deadline.date().isoformat()}). Based on your "
            f"velocity, finishing requires roughly {effective_hours:.0f} focused hours."
        )
        is_active = True
    elif days_buffer < 3:
        alert_text = (
            f"Start now. You have {days_buffer} day(s) of buffer before the safe "
            f"start window closes for the {deadline.date().isoformat()} deadline."
        )
        is_active = True
    else:
        alert_text = (
            f"You can safely start by {recommended_start.date().isoformat()} to hit "
            f"the {deadline.date().isoformat()} deadline at your current velocity "
            f"(~{effective_hours:.0f} hours of focused work)."
        )
        is_active = False

    return DeadmanResult(
        recommended_start=recommended_start,
        days_buffer=days_buffer,
        alert_text=alert_text,
        is_alert_active=is_active,
    )
