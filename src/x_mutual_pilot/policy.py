"""Pure execution policy for approval and live-write gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class PolicyLimits:
    max_actions_per_hour: int = 5
    max_replies_per_day: int = 20
    max_follows_per_day: int = 20


@dataclass(frozen=True)
class PolicyInput:
    action_type: str
    status: str
    expires_at: datetime
    explicit_intent: bool
    risk_flags: tuple[str, ...]
    mode: str
    writes_paused: bool
    environment_writes_paused: bool
    x_auto_reply_approved: bool
    opted_out: bool
    duplicate_execution: bool
    actions_last_hour: int
    actions_today: int
    user_in_cooldown: bool


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate_execution(
    item: PolicyInput,
    limits: PolicyLimits,
    *,
    now: datetime | None = None,
) -> PolicyDecision:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reasons: list[str] = []
    if item.status != "approved":
        reasons.append("approval_required")
    if item.mode == "observe":
        reasons.append("observe_mode_blocks_writes")
    if item.writes_paused or item.environment_writes_paused:
        reasons.append("writes_paused")
    if item.expires_at <= current:
        reasons.append("candidate_expired")
    if item.opted_out:
        reasons.append("target_opted_out")
    if item.duplicate_execution:
        reasons.append("duplicate_execution")
    if item.actions_last_hour >= limits.max_actions_per_hour:
        reasons.append("hourly_limit_reached")
    daily_limit = (
        limits.max_replies_per_day
        if item.action_type == "reply"
        else limits.max_follows_per_day
    )
    if item.actions_today >= daily_limit:
        reasons.append("daily_limit_reached")
    if item.user_in_cooldown:
        reasons.append("user_cooldown_active")
    if item.action_type == "reply":
        if not item.explicit_intent:
            reasons.append("explicit_intent_required")
        if (
            "ai_generated" in item.risk_flags
            and not item.x_auto_reply_approved
        ):
            reasons.append("x_ai_reply_approval_required")
    return PolicyDecision(allowed=not reasons, reasons=tuple(reasons))
