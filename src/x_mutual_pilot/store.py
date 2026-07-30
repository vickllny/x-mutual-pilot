"""SQLite persistence for relationships, candidates, approvals, and audit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Iterable, Mapping
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat()


class StoreError(RuntimeError):
    """Base persistence error."""


class StoreConflict(StoreError):
    """Raised when a requested state transition is no longer valid."""


class Store:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._lock = RLock()

    def close(self) -> None:
        self._connection.close()

    def initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    x_user_id TEXT NOT NULL UNIQUE,
                    mode TEXT NOT NULL,
                    writes_paused INTEGER NOT NULL DEFAULT 1,
                    x_auto_reply_approved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    x_user_id TEXT PRIMARY KEY,
                    username TEXT,
                    display_name TEXT,
                    description TEXT,
                    protected INTEGER NOT NULL DEFAULT 0,
                    verified INTEGER NOT NULL DEFAULT 0,
                    public_metrics TEXT NOT NULL DEFAULT '{}',
                    raw_json TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS relationships (
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    target_user_id TEXT NOT NULL REFERENCES profiles(x_user_id),
                    is_follower INTEGER NOT NULL DEFAULT 0,
                    is_following INTEGER NOT NULL DEFAULT 0,
                    is_mutual INTEGER NOT NULL DEFAULT 0,
                    first_seen_at TEXT NOT NULL,
                    last_changed_at TEXT NOT NULL,
                    PRIMARY KEY (account_id, target_user_id)
                );

                CREATE TABLE IF NOT EXISTS posts (
                    x_post_id TEXT PRIMARY KEY,
                    author_user_id TEXT NOT NULL,
                    conversation_id TEXT,
                    text TEXT NOT NULL,
                    language TEXT,
                    created_at TEXT,
                    received_at TEXT NOT NULL,
                    raw_hash TEXT NOT NULL,
                    possibly_sensitive INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS action_candidates (
                    id TEXT PRIMARY KEY,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    dedupe_key TEXT NOT NULL UNIQUE,
                    action_type TEXT NOT NULL,
                    target_user_id TEXT NOT NULL,
                    target_post_id TEXT,
                    status TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    reasons TEXT NOT NULL,
                    risk_flags TEXT NOT NULL,
                    original_draft TEXT,
                    draft TEXT,
                    explicit_intent INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    rejection_reason TEXT,
                    snoozed_until TEXT
                );

                CREATE TABLE IF NOT EXISTS action_executions (
                    id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL UNIQUE REFERENCES action_candidates(id),
                    idempotency_key TEXT NOT NULL UNIQUE,
                    actor TEXT NOT NULL,
                    request_summary TEXT NOT NULL,
                    x_result_id TEXT,
                    result_status TEXT NOT NULL,
                    error_code TEXT,
                    created_at TEXT NOT NULL,
                    executed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS opt_outs (
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    target_user_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (account_id, target_user_id, scope)
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    candidate_id TEXT,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cursors (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_candidates_status
                    ON action_candidates(account_id, status, created_at);
                CREATE INDEX IF NOT EXISTS idx_executions_time
                    ON action_executions(result_status, executed_at);
                """
            )
            columns = {
                str(row["name"])
                for row in self._connection.execute(
                    "PRAGMA table_info(action_candidates)"
                )
            }
            if "snoozed_until" not in columns:
                self._connection.execute(
                    "ALTER TABLE action_candidates ADD COLUMN snoozed_until TEXT"
                )

    def ensure_account(
        self,
        x_user_id: str,
        *,
        mode: str,
        writes_paused: bool,
        x_auto_reply_approved: bool,
    ) -> int:
        now = _iso()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO accounts (
                    x_user_id, mode, writes_paused, x_auto_reply_approved,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(x_user_id) DO UPDATE SET
                    mode = excluded.mode,
                    writes_paused = CASE
                        WHEN excluded.writes_paused = 1 THEN 1
                        ELSE accounts.writes_paused
                    END,
                    x_auto_reply_approved = excluded.x_auto_reply_approved,
                    updated_at = excluded.updated_at
                """,
                (
                    x_user_id,
                    mode,
                    int(writes_paused),
                    int(x_auto_reply_approved),
                    now,
                    now,
                ),
            )
            row = self._connection.execute(
                "SELECT id FROM accounts WHERE x_user_id = ?", (x_user_id,)
            ).fetchone()
        return int(row["id"])

    def get_account(self, account_id: int) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if row is None:
            raise StoreError("account not found")
        result = dict(row)
        result["writes_paused"] = bool(result["writes_paused"])
        result["x_auto_reply_approved"] = bool(result["x_auto_reply_approved"])
        return result

    def account_by_x_user_id(self, x_user_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT * FROM accounts WHERE x_user_id = ?", (x_user_id,)
        ).fetchone()
        if row is None:
            return None
        return self.get_account(int(row["id"]))

    def _upsert_profile(self, user: Mapping[str, object], now: str) -> None:
        user_id = str(user.get("id", "")).strip()
        if not user_id.isdigit():
            raise StoreError("profile requires a numeric X user id")
        metrics = user.get("public_metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        self._connection.execute(
            """
            INSERT INTO profiles (
                x_user_id, username, display_name, description, protected,
                verified, public_metrics, raw_json, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(x_user_id) DO UPDATE SET
                username = excluded.username,
                display_name = excluded.display_name,
                description = excluded.description,
                protected = excluded.protected,
                verified = excluded.verified,
                public_metrics = excluded.public_metrics,
                raw_json = excluded.raw_json,
                last_seen_at = excluded.last_seen_at
            """,
            (
                user_id,
                user.get("username"),
                user.get("name"),
                user.get("description"),
                int(bool(user.get("protected"))),
                int(bool(user.get("verified"))),
                json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                json.dumps(dict(user), ensure_ascii=False, sort_keys=True),
                now,
            ),
        )

    def sync_relationships(
        self,
        account_id: int,
        *,
        followers: Iterable[Mapping[str, object]],
        following: Iterable[Mapping[str, object]],
    ) -> dict[str, object]:
        follower_map = {str(item["id"]): dict(item) for item in followers}
        following_map = {str(item["id"]): dict(item) for item in following}
        incoming_ids = set(follower_map) | set(following_map)
        initialized_key = f"relationships_initialized:{account_id}"
        initialized = self.get_cursor(initialized_key) == "true"
        now = _iso()

        with self._lock, self._connection:
            existing = {
                str(row["target_user_id"]): bool(row["is_follower"])
                for row in self._connection.execute(
                    "SELECT target_user_id, is_follower FROM relationships "
                    "WHERE account_id = ?",
                    (account_id,),
                )
            }
            new_follower_ids = sorted(
                (
                    user_id
                    for user_id in follower_map
                    if initialized and not existing.get(user_id, False)
                ),
                key=lambda value: (len(value), value),
            )

            for user_id in incoming_ids:
                merged = dict(follower_map.get(user_id, {}))
                merged.update(following_map.get(user_id, {}))
                self._upsert_profile(merged, now)

            all_ids = set(existing) | incoming_ids
            for user_id in all_ids:
                is_follower = user_id in follower_map
                is_following = user_id in following_map
                self._connection.execute(
                    """
                    INSERT INTO relationships (
                        account_id, target_user_id, is_follower, is_following,
                        is_mutual, first_seen_at, last_changed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, target_user_id) DO UPDATE SET
                        is_follower = excluded.is_follower,
                        is_following = excluded.is_following,
                        is_mutual = excluded.is_mutual,
                        last_changed_at = CASE
                            WHEN relationships.is_follower != excluded.is_follower
                              OR relationships.is_following != excluded.is_following
                            THEN excluded.last_changed_at
                            ELSE relationships.last_changed_at
                        END
                    """,
                    (
                        account_id,
                        user_id,
                        int(is_follower),
                        int(is_following),
                        int(is_follower and is_following),
                        now,
                        now,
                    ),
                )
            self._set_cursor_locked(initialized_key, "true", now)

        return {
            "new_follower_ids": new_follower_ids,
            "followers": len(follower_map),
            "following": len(following_map),
            "mutuals": len(set(follower_map) & set(following_map)),
        }

    def get_profile(self, user_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT * FROM profiles WHERE x_user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["id"] = result.pop("x_user_id")
        result["name"] = result.pop("display_name")
        result["protected"] = bool(result["protected"])
        result["verified"] = bool(result["verified"])
        result["public_metrics"] = json.loads(str(result["public_metrics"]))
        result.pop("raw_json", None)
        return result

    def mutual_user_ids(self, account_id: int) -> list[str]:
        rows = self._connection.execute(
            "SELECT target_user_id FROM relationships "
            "WHERE account_id = ? AND is_mutual = 1",
            (account_id,),
        )
        return sorted(
            (str(row["target_user_id"]) for row in rows),
            key=lambda value: (len(value), value),
        )

    def create_candidate(
        self,
        account_id: int,
        *,
        action_type: str,
        target_user_id: str,
        target_post_id: str | None,
        score: int,
        reasons: Iterable[str],
        risk_flags: Iterable[str],
        draft: str | None,
        explicit_intent: bool,
        expires_in_minutes: int,
    ) -> str:
        dedupe_key = f"{account_id}:{action_type}:{target_user_id}:{target_post_id or '-'}"
        existing = self._connection.execute(
            "SELECT id FROM action_candidates WHERE dedupe_key = ?", (dedupe_key,)
        ).fetchone()
        if existing is not None:
            return str(existing["id"])

        candidate_id = uuid4().hex
        now = utc_now()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO action_candidates (
                    id, account_id, dedupe_key, action_type, target_user_id,
                    target_post_id, status, score, reasons, risk_flags,
                    original_draft, draft, explicit_intent, expires_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    account_id,
                    dedupe_key,
                    action_type,
                    target_user_id,
                    target_post_id,
                    max(0, min(100, int(score))),
                    json.dumps(list(reasons), ensure_ascii=False),
                    json.dumps(list(risk_flags), ensure_ascii=False),
                    draft,
                    draft,
                    int(explicit_intent),
                    _iso(now + timedelta(minutes=expires_in_minutes)),
                    _iso(now),
                    _iso(now),
                ),
            )
            self._audit_locked(
                "candidate.created",
                "system",
                candidate_id,
                {"action_type": action_type, "score": score},
            )
        return candidate_id

    @staticmethod
    def _candidate_dict(row: sqlite3.Row) -> dict[str, object]:
        result = dict(row)
        result["reasons"] = json.loads(str(result["reasons"]))
        result["risk_flags"] = json.loads(str(result["risk_flags"]))
        result["explicit_intent"] = bool(result["explicit_intent"])
        return result

    def get_candidate(self, candidate_id: str) -> dict[str, object]:
        row = self._connection.execute(
            "SELECT * FROM action_candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if row is None:
            raise StoreError("candidate not found")
        return self._candidate_dict(row)

    def list_candidates(
        self, account_id: int, *, status: str | None = None, limit: int = 100
    ) -> list[dict[str, object]]:
        self.refresh_candidate_states()
        query = "SELECT * FROM action_candidates WHERE account_id = ?"
        params: list[object] = [account_id]
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [
            self._candidate_dict(row)
            for row in self._connection.execute(query, params)
        ]

    def approve_candidate(
        self,
        candidate_id: str,
        *,
        actor: str,
        edited_draft: str | None = None,
    ) -> None:
        now = _iso()
        with self._lock, self._connection:
            candidate = self.get_candidate(candidate_id)
            if candidate["status"] != "pending":
                raise StoreConflict("only pending candidates can be approved")
            draft = edited_draft if edited_draft is not None else candidate["draft"]
            updated = self._connection.execute(
                """
                UPDATE action_candidates
                SET status = 'approved', draft = ?, approved_by = ?,
                    approved_at = ?, updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (draft, actor, now, now, candidate_id),
            )
            if updated.rowcount != 1:
                raise StoreConflict("candidate changed before approval")
            self._audit_locked(
                "candidate.approved",
                actor,
                candidate_id,
                {"draft_edited": edited_draft is not None},
            )

    def reject_candidate(
        self, candidate_id: str, *, actor: str, reason: str
    ) -> None:
        now = _iso()
        with self._lock, self._connection:
            updated = self._connection.execute(
                """
                UPDATE action_candidates
                SET status = 'rejected', rejection_reason = ?, updated_at = ?
                WHERE id = ? AND status IN ('pending', 'approved')
                """,
                (reason, now, candidate_id),
            )
            if updated.rowcount != 1:
                raise StoreConflict("candidate cannot be rejected in its current state")
            self._audit_locked(
                "candidate.rejected", actor, candidate_id, {"reason": reason}
            )

    def snooze_candidate(
        self, candidate_id: str, *, actor: str, minutes: int
    ) -> None:
        if minutes <= 0:
            raise StoreError("snooze minutes must be positive")
        now = utc_now()
        with self._lock, self._connection:
            updated = self._connection.execute(
                """
                UPDATE action_candidates
                SET status = 'snoozed', snoozed_until = ?, updated_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (
                    _iso(now + timedelta(minutes=minutes)),
                    _iso(now),
                    candidate_id,
                ),
            )
            if updated.rowcount != 1:
                raise StoreConflict("only pending candidates can be snoozed")
            self._audit_locked(
                "candidate.snoozed",
                actor,
                candidate_id,
                {"minutes": minutes},
            )

    def refresh_candidate_states(self, *, now: datetime | None = None) -> None:
        current = _iso(now)
        with self._lock, self._connection:
            self._connection.execute(
                """
                UPDATE action_candidates
                SET status = 'pending', snoozed_until = NULL, updated_at = ?
                WHERE status = 'snoozed' AND snoozed_until <= ?
                  AND expires_at > ?
                """,
                (current, current, current),
            )
            self._connection.execute(
                """
                UPDATE action_candidates
                SET status = 'expired', updated_at = ?
                WHERE status IN ('pending', 'approved', 'snoozed')
                  AND expires_at <= ?
                """,
                (current, current),
            )

    def set_writes_paused(self, account_id: int, paused: bool, *, actor: str) -> None:
        with self._lock, self._connection:
            updated = self._connection.execute(
                "UPDATE accounts SET writes_paused = ?, updated_at = ? WHERE id = ?",
                (int(paused), _iso(), account_id),
            )
            if updated.rowcount != 1:
                raise StoreError("account not found")
            self._audit_locked(
                "writes.paused" if paused else "writes.resumed",
                actor,
                None,
                {"account_id": account_id},
            )

    def add_opt_out(
        self, account_id: int, target_user_id: str, scope: str, reason: str
    ) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO opt_outs (
                    account_id, target_user_id, scope, reason, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_id, target_user_id, scope) DO UPDATE SET
                    reason = excluded.reason
                """,
                (account_id, target_user_id, scope, reason, _iso()),
            )

    def is_opted_out(
        self, account_id: int, target_user_id: str, scope: str
    ) -> bool:
        row = self._connection.execute(
            """
            SELECT 1 FROM opt_outs
            WHERE account_id = ? AND target_user_id = ?
              AND scope IN ('all', ?)
            LIMIT 1
            """,
            (account_id, target_user_id, scope),
        ).fetchone()
        return row is not None

    def save_post(self, post: Mapping[str, object]) -> bool:
        post_id = str(post.get("id", ""))
        if not post_id.isdigit():
            raise StoreError("post requires a numeric id")
        text = str(post.get("text", ""))
        import hashlib

        raw = json.dumps(dict(post), ensure_ascii=False, sort_keys=True)
        with self._lock, self._connection:
            inserted = self._connection.execute(
                """
                INSERT OR IGNORE INTO posts (
                    x_post_id, author_user_id, conversation_id, text, language,
                    created_at, received_at, raw_hash, possibly_sensitive, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post_id,
                    str(post.get("author_id", "")),
                    post.get("conversation_id"),
                    text,
                    post.get("lang"),
                    post.get("created_at"),
                    _iso(),
                    hashlib.sha256(raw.encode()).hexdigest(),
                    int(bool(post.get("possibly_sensitive"))),
                    raw,
                ),
            )
        return inserted.rowcount == 1

    def get_cursor(self, key: str) -> str | None:
        row = self._connection.execute(
            "SELECT value FROM cursors WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else str(row["value"])

    def _set_cursor_locked(self, key: str, value: str, now: str) -> None:
        self._connection.execute(
            """
            INSERT INTO cursors (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )

    def set_cursor(self, key: str, value: str) -> None:
        with self._lock, self._connection:
            self._set_cursor_locked(key, value, _iso())

    def successful_execution_exists(self, candidate_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM action_executions "
            "WHERE candidate_id = ? AND result_status = 'succeeded'",
            (candidate_id,),
        ).fetchone()
        return row is not None

    def successful_action_count(
        self, account_id: int, action_type: str, since: datetime
    ) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM action_executions e
            JOIN action_candidates c ON c.id = e.candidate_id
            WHERE c.account_id = ? AND c.action_type = ?
              AND e.result_status = 'succeeded' AND e.executed_at >= ?
            """,
            (account_id, action_type, _iso(since)),
        ).fetchone()
        return int(row["count"])

    def user_has_recent_action(
        self,
        account_id: int,
        target_user_id: str,
        action_type: str,
        since: datetime,
    ) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM action_executions e
            JOIN action_candidates c ON c.id = e.candidate_id
            WHERE c.account_id = ? AND c.target_user_id = ?
              AND c.action_type = ? AND e.result_status = 'succeeded'
              AND e.executed_at >= ?
            LIMIT 1
            """,
            (account_id, target_user_id, action_type, _iso(since)),
        ).fetchone()
        return row is not None

    def begin_execution(
        self, candidate_id: str, *, actor: str
    ) -> dict[str, object]:
        execution_id = uuid4().hex
        now = _iso()
        with self._lock, self._connection:
            candidate = self.get_candidate(candidate_id)
            if candidate["status"] != "approved":
                raise StoreConflict("candidate is not approved")
            updated = self._connection.execute(
                "UPDATE action_candidates SET status = 'executing', updated_at = ? "
                "WHERE id = ? AND status = 'approved'",
                (now, candidate_id),
            )
            if updated.rowcount != 1:
                raise StoreConflict("candidate changed before execution")
            self._connection.execute(
                """
                INSERT INTO action_executions (
                    id, candidate_id, idempotency_key, actor, request_summary,
                    result_status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'running', ?)
                """,
                (
                    execution_id,
                    candidate_id,
                    f"candidate:{candidate_id}",
                    actor,
                    json.dumps(
                        {
                            "action_type": candidate["action_type"],
                            "target_user_id": candidate["target_user_id"],
                            "target_post_id": candidate["target_post_id"],
                        },
                        sort_keys=True,
                    ),
                    now,
                ),
            )
            self._audit_locked(
                "execution.started", actor, candidate_id, {"execution_id": execution_id}
            )
        return {"id": execution_id, "candidate_id": candidate_id}

    def finish_execution(
        self,
        execution_id: str,
        *,
        succeeded: bool,
        x_result_id: str | None = None,
        error_code: str | None = None,
    ) -> dict[str, object]:
        status = "succeeded" if succeeded else "failed"
        candidate_status = "executed" if succeeded else "failed"
        now = _iso()
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT candidate_id FROM action_executions WHERE id = ?",
                (execution_id,),
            ).fetchone()
            if row is None:
                raise StoreError("execution not found")
            candidate_id = str(row["candidate_id"])
            self._connection.execute(
                """
                UPDATE action_executions
                SET result_status = ?, x_result_id = ?, error_code = ?,
                    executed_at = ?
                WHERE id = ? AND result_status = 'running'
                """,
                (status, x_result_id, error_code, now, execution_id),
            )
            self._connection.execute(
                "UPDATE action_candidates SET status = ?, updated_at = ? WHERE id = ?",
                (candidate_status, now, candidate_id),
            )
            self._audit_locked(
                f"execution.{status}",
                "system",
                candidate_id,
                {
                    "execution_id": execution_id,
                    "x_result_id": x_result_id,
                    "error_code": error_code,
                },
            )
        return {
            "id": execution_id,
            "candidate_id": candidate_id,
            "result_status": status,
            "x_result_id": x_result_id,
            "error_code": error_code,
        }

    def dashboard_counts(self, account_id: int) -> dict[str, int]:
        result: dict[str, int] = {}
        self.refresh_candidate_states()
        for status in (
            "pending",
            "approved",
            "snoozed",
            "expired",
            "executed",
            "failed",
            "rejected",
        ):
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM action_candidates "
                "WHERE account_id = ? AND status = ?",
                (account_id, status),
            ).fetchone()
            result[status] = int(row["count"])
        for name, condition in (
            ("followers", "is_follower = 1"),
            ("following", "is_following = 1"),
            ("mutuals", "is_mutual = 1"),
        ):
            row = self._connection.execute(
                f"SELECT COUNT(*) AS count FROM relationships "
                f"WHERE account_id = ? AND {condition}",
                (account_id,),
            ).fetchone()
            result[name] = int(row["count"])
        return result

    def recent_audit(self, limit: int = 50) -> list[dict[str, object]]:
        return [
            dict(row)
            for row in self._connection.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]

    def active_alerts(self, account_id: int) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        account = self.get_account(account_id)
        if account["writes_paused"]:
            alerts.append(
                {
                    "level": "info",
                    "code": "writes_paused",
                    "message": "Write operations are paused.",
                }
            )
        since = _iso(utc_now() - timedelta(days=1))
        failures = self._connection.execute(
            """
            SELECT e.error_code, COUNT(*) AS count
            FROM action_executions e
            JOIN action_candidates c ON c.id = e.candidate_id
            WHERE c.account_id = ? AND e.result_status = 'failed'
              AND e.executed_at >= ?
            GROUP BY e.error_code
            """,
            (account_id, since),
        )
        for row in failures:
            code = str(row["error_code"] or "unknown")
            count = int(row["count"])
            level = "critical" if code in {"401", "403"} else "warning"
            alerts.append(
                {
                    "level": level,
                    "code": f"x_api_{code}",
                    "message": f"{count} failed execution(s) with error {code}.",
                }
            )
        pending = self.dashboard_counts(account_id)["pending"]
        if pending > 100:
            alerts.append(
                {
                    "level": "warning",
                    "code": "approval_backlog",
                    "message": f"Approval backlog is {pending} candidates.",
                }
            )
        return alerts

    def _audit_locked(
        self,
        event_type: str,
        actor: str,
        candidate_id: str | None,
        details: Mapping[str, object],
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO audit_log (
                event_type, actor, candidate_id, details_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_type,
                actor,
                candidate_id,
                json.dumps(dict(details), ensure_ascii=False, sort_keys=True),
                _iso(),
            ),
        )
