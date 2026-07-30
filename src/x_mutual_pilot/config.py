"""Environment configuration with secret-safe diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import os
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


@dataclass(frozen=True)
class Settings:
    bearer_token: str
    account_user_id: str
    mode: str
    writes_paused: bool
    api_base_url: str = "https://api.x.com/2"

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "Settings":
        env = os.environ if environment is None else environment
        token = env.get("X_BEARER_TOKEN", "").strip()
        user_id = env.get("X_ACCOUNT_USER_ID", "").strip()
        mode = env.get("X_AGENT_MODE", "observe").strip().lower()
        writes_paused = _parse_bool(
            env.get("X_WRITES_PAUSED", "true"), "X_WRITES_PAUSED"
        )
        api_base_url = "https://api.x.com/2"

        if not token:
            raise ConfigError("X_BEARER_TOKEN is required")
        if not USER_ID_PATTERN.fullmatch(user_id):
            raise ConfigError("X_ACCOUNT_USER_ID must contain 1 to 19 digits")
        if mode not in VALID_MODES:
            raise ConfigError(
                "X_AGENT_MODE must be observe, assisted, or controlled-auto"
            )
        return cls(
            bearer_token=token,
            account_user_id=user_id,
            mode=mode,
            writes_paused=writes_paused,
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
        "api_base_url": settings.api_base_url,
    }
