"""Execute already-approved actions with policy and idempotency gates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .policy import PolicyInput, PolicyLimits, evaluate_execution
from .store import Store, StoreConflict
from .x_api import XApiError


class ExecutionBlocked(RuntimeError):
    """Raised before any network write when a gate fails."""


class ActionExecutor:
    def __init__(
        self,
        store: Store,
        client: object,
        *,
        environment_writes_paused: bool,
        limits: PolicyLimits,
        user_cooldown_hours: int = 24,
    ) -> None:
        self._store = store
        self._client = client
        self._environment_writes_paused = environment_writes_paused
        self._limits = limits
        self._cooldown = user_cooldown_hours

    def execute(self, candidate_id: str, *, actor: str) -> dict[str, object]:
        candidate = self._store.get_candidate(candidate_id)
        account = self._store.get_account(int(candidate["account_id"]))
        now = datetime.now(timezone.utc)
        action_type = str(candidate["action_type"])
        account_id = int(account["id"])
        target_user_id = str(candidate["target_user_id"])
        decision = evaluate_execution(
            PolicyInput(
                action_type=action_type,
                status=str(candidate["status"]),
                expires_at=datetime.fromisoformat(str(candidate["expires_at"])),
                explicit_intent=bool(candidate["explicit_intent"]),
                risk_flags=tuple(str(item) for item in candidate["risk_flags"]),
                mode=str(account["mode"]),
                writes_paused=bool(account["writes_paused"]),
                environment_writes_paused=self._environment_writes_paused,
                x_auto_reply_approved=bool(account["x_auto_reply_approved"]),
                opted_out=self._store.is_opted_out(
                    account_id, target_user_id, action_type
                ),
                duplicate_execution=self._store.successful_execution_exists(
                    candidate_id
                ),
                actions_last_hour=self._store.successful_action_count(
                    account_id, action_type, now - timedelta(hours=1)
                ),
                actions_today=self._store.successful_action_count(
                    account_id, action_type, now - timedelta(days=1)
                ),
                user_in_cooldown=self._store.user_has_recent_action(
                    account_id,
                    target_user_id,
                    action_type,
                    now - timedelta(hours=self._cooldown),
                ),
            ),
            self._limits,
            now=now,
        )
        if not decision.allowed:
            raise ExecutionBlocked(", ".join(decision.reasons))

        try:
            execution = self._store.begin_execution(candidate_id, actor=actor)
        except StoreConflict as error:
            raise ExecutionBlocked(str(error)) from error

        try:
            if action_type == "follow":
                result = self._client.follow_user(
                    str(account["x_user_id"]), target_user_id
                )
                if not (result.get("following") or result.get("pending_follow")):
                    raise XApiError("X API did not confirm the follow request")
                x_result_id = target_user_id
            elif action_type == "reply":
                post_id = str(candidate["target_post_id"] or "")
                self._client.get_post(post_id)
                draft = str(candidate["draft"] or "").strip()
                if not draft:
                    raise ExecutionBlocked("approved reply draft is empty")
                result = self._client.create_reply(
                    draft,
                    post_id,
                    made_with_ai="ai_generated" in candidate["risk_flags"],
                )
                x_result_id = str(result.get("id") or "")
                if not x_result_id:
                    raise XApiError("X API did not return a reply id")
            else:
                raise ExecutionBlocked("unsupported action type")
        except ExecutionBlocked:
            self._store.finish_execution(
                str(execution["id"]), succeeded=False, error_code="policy"
            )
            raise
        except XApiError as error:
            if error.status in {401, 403}:
                self._store.set_writes_paused(
                    account_id, True, actor="system:x-api"
                )
            self._store.finish_execution(
                str(execution["id"]),
                succeeded=False,
                error_code=str(error.status or "network"),
            )
            raise
        except Exception:
            self._store.finish_execution(
                str(execution["id"]), succeeded=False, error_code="uncertain"
            )
            raise

        return self._store.finish_execution(
            str(execution["id"]), succeeded=True, x_result_id=x_result_id
        )
