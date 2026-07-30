"""Environment configuration with secret-safe diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Mapping


VALID_MODES = {"observe", "assisted", "controlled-auto"}
USER_ID_PATTERN = re.compile(r"^[0-9]{1,19}$")
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """Raised when runtime configuration is unsafe or incomplete."""


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ConfigError(f"{name} must be true or false")


def _parse_positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigError(f"{name} must be a positive integer") from error
    if parsed <= 0:
        raise ConfigError(f"{name} must be a positive integer")
    return parsed


@dataclass(frozen=True)
class Settings:
    bearer_token: str
    account_user_id: str
    mode: str
    writes_paused: bool
    user_access_token: str | None = None
    x_auto_reply_approved: bool = False
    controlled_auto_enabled: bool = False
    database_path: Path = Path("data/x-mutual-pilot.sqlite3")
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    account_topics: tuple[str, ...] = ()
    blocked_terms: tuple[str, ...] = ()
    approval_expiry_minutes: int = 120
    max_actions_per_hour: int = 5
    max_replies_per_day: int = 20
    max_follows_per_day: int = 20
    user_reply_cooldown_hours: int = 24
    api_base_url: str = "https://api.x.com/2"

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        require_read_credentials: bool = True,
    ) -> "Settings":
        env = os.environ if environment is None else environment
        token = env.get("X_BEARER_TOKEN", "").strip()
        user_id = env.get("X_ACCOUNT_USER_ID", "").strip()
        mode = env.get("X_AGENT_MODE", "observe").strip().lower()
        writes_paused = _parse_bool(
            env.get("X_WRITES_PAUSED", "true"), "X_WRITES_PAUSED"
        )
        user_access_token = env.get("X_USER_ACCESS_TOKEN", "").strip() or None
        x_auto_reply_approved = _parse_bool(
            env.get("X_AI_REPLY_APPROVED", "false"), "X_AI_REPLY_APPROVED"
        )
        controlled_auto_enabled = _parse_bool(
            env.get("X_CONTROLLED_AUTO_ENABLED", "false"),
            "X_CONTROLLED_AUTO_ENABLED",
        )
        database_path = Path(
            env.get("X_DATABASE_PATH", "data/x-mutual-pilot.sqlite3")
        )
        openai_api_key = env.get("OPENAI_API_KEY", "").strip() or None
        openai_model = env.get("OPENAI_MODEL", "gpt-5.6-luna").strip()
        account_topics = tuple(
            topic.strip()
            for topic in env.get("X_ACCOUNT_TOPICS", "").split(",")
            if topic.strip()
        )
        blocked_terms = tuple(
            term.strip()
            for term in env.get("X_BLOCKED_TERMS", "").split(",")
            if term.strip()
        )
        approval_expiry_minutes = _parse_positive_int(
            env.get("APPROVAL_EXPIRY_MINUTES", "120"),
            "APPROVAL_EXPIRY_MINUTES",
        )
        max_actions_per_hour = _parse_positive_int(
            env.get("MAX_ACTIONS_PER_HOUR", "5"), "MAX_ACTIONS_PER_HOUR"
        )
        max_replies_per_day = _parse_positive_int(
            env.get("MAX_REPLIES_PER_DAY", "20"), "MAX_REPLIES_PER_DAY"
        )
        max_follows_per_day = _parse_positive_int(
            env.get("MAX_FOLLOWS_PER_DAY", "20"), "MAX_FOLLOWS_PER_DAY"
        )
        user_reply_cooldown_hours = _parse_positive_int(
            env.get("USER_REPLY_COOLDOWN_HOURS", "24"),
            "USER_REPLY_COOLDOWN_HOURS",
        )
        api_base_url = "https://api.x.com/2"

        if require_read_credentials and not token:
            raise ConfigError("X_BEARER_TOKEN is required")
        if not USER_ID_PATTERN.fullmatch(user_id):
            raise ConfigError("X_ACCOUNT_USER_ID must contain 1 to 19 digits")
        if mode not in VALID_MODES:
            raise ConfigError(
                "X_AGENT_MODE must be observe, assisted, or controlled-auto"
            )
        if controlled_auto_enabled and mode != "controlled-auto":
            raise ConfigError(
                "X_CONTROLLED_AUTO_ENABLED requires X_AGENT_MODE=controlled-auto"
            )
        if controlled_auto_enabled and not x_auto_reply_approved:
            raise ConfigError(
                "controlled auto requires X_AI_REPLY_APPROVED=true"
            )
        return cls(
            bearer_token=token,
            account_user_id=user_id,
            mode=mode,
            writes_paused=writes_paused,
            user_access_token=user_access_token,
            x_auto_reply_approved=x_auto_reply_approved,
            controlled_auto_enabled=controlled_auto_enabled,
            database_path=database_path,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            account_topics=account_topics,
            blocked_terms=blocked_terms,
            approval_expiry_minutes=approval_expiry_minutes,
            max_actions_per_hour=max_actions_per_hour,
            max_replies_per_day=max_replies_per_day,
            max_follows_per_day=max_follows_per_day,
            user_reply_cooldown_hours=user_reply_cooldown_hours,
            api_base_url=api_base_url,
        )


def environment_diagnostics(
    environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    env = os.environ if environment is None else environment
    try:
        settings = Settings.from_environment(env)
    except ConfigError as error:
        return {
            "ready": False,
            "error": str(error),
            "mode": env.get("X_AGENT_MODE", "observe"),
            "writes_paused": env.get("X_WRITES_PAUSED", "true"),
            "bearer_token_configured": bool(env.get("X_BEARER_TOKEN", "").strip()),
            "account_user_id_configured": bool(
                env.get("X_ACCOUNT_USER_ID", "").strip()
            ),
        }

    return {
        "ready": True,
        "mode": settings.mode,
        "writes_paused": settings.writes_paused,
        "bearer_token_configured": True,
        "account_user_id_configured": True,
        "user_access_token_configured": bool(settings.user_access_token),
        "x_auto_reply_approved": settings.x_auto_reply_approved,
        "controlled_auto_enabled": settings.controlled_auto_enabled,
        "openai_configured": bool(settings.openai_api_key),
        "database_path": str(settings.database_path),
        "api_base_url": settings.api_base_url,
    }
