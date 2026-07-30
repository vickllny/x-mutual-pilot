"""Command-line entry point for discovery, approval, and controlled execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import ConfigError, Settings, environment_diagnostics
from .drafts import DraftError, LocalDraftGenerator, OpenAIDraftGenerator
from .executor import ActionExecutor, ExecutionBlocked
from .policy import PolicyLimits
from .relationships import RelationshipDataError, build_relationship_snapshot
from .scoring import FollowBackScorer
from .safety import ContentSafetyFilter
from .services import PostWatcher, RelationshipSyncService
from .store import Store, StoreConflict, StoreError
from .web import serve_dashboard
from .x_api import XApiClient, XApiError


def _write_json(payload: object, output: Path | None = None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def _settings(*, require_read_credentials: bool = True) -> Settings:
    return Settings.from_environment(
        require_read_credentials=require_read_credentials
    )


def _open_store(settings: Settings) -> tuple[Store, int]:
    store = Store(settings.database_path)
    store.initialize()
    account_id = store.ensure_account(
        settings.account_user_id,
        mode=settings.mode,
        writes_paused=settings.writes_paused,
        x_auto_reply_approved=settings.x_auto_reply_approved,
    )
    return store, account_id


def _client(settings: Settings) -> XApiClient:
    return XApiClient(
        settings.bearer_token,
        user_access_token=settings.user_access_token,
        base_url=settings.api_base_url,
    )


def _limits(settings: Settings) -> PolicyLimits:
    return PolicyLimits(
        max_actions_per_hour=settings.max_actions_per_hour,
        max_replies_per_day=settings.max_replies_per_day,
        max_follows_per_day=settings.max_follows_per_day,
    )


def _draft_generator(settings: Settings) -> object:
    if settings.openai_api_key:
        return OpenAIDraftGenerator(
            settings.openai_api_key, model=settings.openai_model
        )
    return LocalDraftGenerator()


def _doctor(_: argparse.Namespace) -> int:
    diagnostics = environment_diagnostics()
    _write_json(diagnostics)
    return 0 if diagnostics["ready"] else 2


def _init_db(_: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, account_id = _open_store(settings)
    try:
        _write_json(
            {
                "initialized": True,
                "database_path": str(settings.database_path),
                "account_id": account_id,
            }
        )
    finally:
        store.close()
    return 0


def _sync_relationships(args: argparse.Namespace) -> int:
    settings = _settings()
    client = _client(settings)
    store, account_id = _open_store(settings)
    try:
        followers = client.followers(settings.account_user_id)
        following = client.following(settings.account_user_id)
        snapshot = build_relationship_snapshot(
            settings.account_user_id, followers, following
        )
        changes = store.sync_relationships(
            account_id, followers=followers, following=following
        )
        scorer = FollowBackScorer(settings.account_topics)
        candidates = 0
        for user_id in changes["new_follower_ids"]:
            profile = store.get_profile(str(user_id))
            if profile is None:
                continue
            result = scorer.score(profile)
            if result["decision"] == "reject":
                continue
            store.create_candidate(
                account_id,
                action_type="follow",
                target_user_id=str(user_id),
                target_post_id=None,
                score=int(result["score"]),
                reasons=result["reasons"],
                risk_flags=result["riskFlags"],
                draft=None,
                explicit_intent=False,
                expires_in_minutes=settings.approval_expiry_minutes,
            )
            candidates += 1
        snapshot["runtime"] = {
            "mode": settings.mode,
            "writes_paused": settings.writes_paused,
            "read_only": True,
        }
        snapshot["changes"] = {**changes, "follow_candidates_created": candidates}
        _write_json(snapshot, args.output)
    finally:
        store.close()
    return 0


def _poll_posts(args: argparse.Namespace) -> int:
    settings = _settings()
    store, account_id = _open_store(settings)
    try:
        watcher = PostWatcher(
            store,
            _client(settings),
            _draft_generator(settings),
            approval_expiry_minutes=settings.approval_expiry_minutes,
            controlled_auto_enabled=settings.controlled_auto_enabled,
            content_filter=ContentSafetyFilter(settings.blocked_terms),
        )
        _write_json(
            watcher.poll(
                account_id,
                settings.account_user_id,
                limit_users=args.limit_users,
            )
        )
    finally:
        store.close()
    return 0


def _run_cycle(args: argparse.Namespace) -> int:
    settings = _settings()
    store, account_id = _open_store(settings)
    try:
        client = _client(settings)
        sync_result = RelationshipSyncService(
            store,
            client,
            FollowBackScorer(settings.account_topics),
            approval_expiry_minutes=settings.approval_expiry_minutes,
        ).sync(account_id, settings.account_user_id)
        poll_result = PostWatcher(
            store,
            client,
            _draft_generator(settings),
            approval_expiry_minutes=settings.approval_expiry_minutes,
            controlled_auto_enabled=settings.controlled_auto_enabled,
            content_filter=ContentSafetyFilter(settings.blocked_terms),
        ).poll(account_id, settings.account_user_id, limit_users=args.limit_users)
        executed: list[dict[str, object]] = []
        if settings.controlled_auto_enabled:
            if not settings.user_access_token:
                raise ConfigError(
                    "X_USER_ACCESS_TOKEN is required for controlled auto"
                )
            executor = ActionExecutor(
                store,
                client,
                environment_writes_paused=settings.writes_paused,
                limits=_limits(settings),
                user_cooldown_hours=settings.user_reply_cooldown_hours,
            )
            for candidate in store.list_candidates(
                account_id, status="approved", limit=100
            ):
                if candidate.get("approved_by") != "controlled-auto":
                    continue
                executed.append(
                    executor.execute(str(candidate["id"]), actor="controlled-auto")
                )
        _write_json(
            {"relationships": sync_result, "posts": poll_result, "executed": executed}
        )
    finally:
        store.close()
    return 0


def _list_candidates(args: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, account_id = _open_store(settings)
    try:
        _write_json(
            store.list_candidates(account_id, status=args.status, limit=args.limit)
        )
    finally:
        store.close()
    return 0


def _approve(args: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, _ = _open_store(settings)
    try:
        store.approve_candidate(
            args.candidate_id, actor=args.actor, edited_draft=args.draft
        )
        _write_json({"approved": args.candidate_id})
    finally:
        store.close()
    return 0


def _reject(args: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, _ = _open_store(settings)
    try:
        store.reject_candidate(
            args.candidate_id, actor=args.actor, reason=args.reason
        )
        _write_json({"rejected": args.candidate_id})
    finally:
        store.close()
    return 0


def _snooze(args: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, _ = _open_store(settings)
    try:
        store.snooze_candidate(
            args.candidate_id, actor=args.actor, minutes=args.minutes
        )
        _write_json(
            {"snoozed": args.candidate_id, "minutes": args.minutes}
        )
    finally:
        store.close()
    return 0


def _execute(args: argparse.Namespace) -> int:
    if not args.confirm_live_write:
        raise ConfigError("execute requires --confirm-live-write")
    settings = _settings()
    if not settings.user_access_token:
        raise ConfigError("X_USER_ACCESS_TOKEN is required for writes")
    store, _ = _open_store(settings)
    try:
        result = ActionExecutor(
            store,
            _client(settings),
            environment_writes_paused=settings.writes_paused,
            limits=_limits(settings),
            user_cooldown_hours=settings.user_reply_cooldown_hours,
        ).execute(args.candidate_id, actor=args.actor)
        _write_json(result)
    finally:
        store.close()
    return 0


def _set_pause(args: argparse.Namespace, paused: bool) -> int:
    settings = _settings(require_read_credentials=False)
    if not paused and not args.confirm_resume:
        raise ConfigError("resume requires --confirm-resume")
    store, account_id = _open_store(settings)
    try:
        store.set_writes_paused(account_id, paused, actor=args.actor)
        _write_json(
            {
                "writes_paused": paused,
                "environment_writes_paused": settings.writes_paused,
            }
        )
    finally:
        store.close()
    return 0


def _opt_out(args: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, account_id = _open_store(settings)
    try:
        store.add_opt_out(
            account_id, args.user_id, args.scope, args.reason
        )
        _write_json({"opted_out": args.user_id, "scope": args.scope})
    finally:
        store.close()
    return 0


def _status(_: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, account_id = _open_store(settings)
    try:
        _write_json(
            {
                "account": store.get_account(account_id),
                "counts": store.dashboard_counts(account_id),
                "alerts": store.active_alerts(account_id),
                "recent_audit": store.recent_audit(20),
                "environment_writes_paused": settings.writes_paused,
            }
        )
    finally:
        store.close()
    return 0


def _serve(args: argparse.Namespace) -> int:
    settings = _settings(require_read_credentials=False)
    store, account_id = _open_store(settings)
    try:
        sys.stderr.write(f"dashboard: http://{args.host}:{args.port}\n")
        try:
            serve_dashboard(store, account_id, host=args.host, port=args.port)
        except KeyboardInterrupt:
            sys.stderr.write("dashboard stopped\n")
    finally:
        store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x-mutual-pilot",
        description="Discover, review, and safely execute X interactions.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="validate secret-safe configuration")
    doctor.set_defaults(handler=_doctor)

    init_db = subparsers.add_parser("init-db", help="initialize SQLite state")
    init_db.set_defaults(handler=_init_db)

    sync = subparsers.add_parser(
        "sync-relationships", help="sync followers/following and score new followers"
    )
    sync.add_argument("--output", type=Path)
    sync.set_defaults(handler=_sync_relationships)

    poll = subparsers.add_parser(
        "poll-posts", help="discover mutual posts and explicit mentions"
    )
    poll.add_argument("--limit-users", type=int, default=100)
    poll.set_defaults(handler=_poll_posts)

    cycle = subparsers.add_parser(
        "run-cycle", help="sync, discover, and run fully gated controlled-auto actions"
    )
    cycle.add_argument("--limit-users", type=int, default=100)
    cycle.set_defaults(handler=_run_cycle)

    listing = subparsers.add_parser("list-candidates", help="list approval items")
    listing.add_argument("--status")
    listing.add_argument("--limit", type=int, default=100)
    listing.set_defaults(handler=_list_candidates)

    approve = subparsers.add_parser("approve", help="approve one pending candidate")
    approve.add_argument("candidate_id")
    approve.add_argument("--actor", required=True)
    approve.add_argument("--draft")
    approve.set_defaults(handler=_approve)

    reject = subparsers.add_parser("reject", help="reject one candidate")
    reject.add_argument("candidate_id")
    reject.add_argument("--actor", required=True)
    reject.add_argument("--reason", required=True)
    reject.set_defaults(handler=_reject)

    snooze = subparsers.add_parser("snooze", help="snooze a pending candidate")
    snooze.add_argument("candidate_id")
    snooze.add_argument("--actor", required=True)
    snooze.add_argument("--minutes", type=int, default=60)
    snooze.set_defaults(handler=_snooze)

    execute = subparsers.add_parser(
        "execute", help="execute one approved candidate after all policy checks"
    )
    execute.add_argument("candidate_id")
    execute.add_argument("--actor", required=True)
    execute.add_argument("--confirm-live-write", action="store_true")
    execute.set_defaults(handler=_execute)

    pause = subparsers.add_parser("pause", help="persistently pause writes")
    pause.add_argument("--actor", required=True)
    pause.set_defaults(handler=lambda args: _set_pause(args, True))

    resume = subparsers.add_parser("resume", help="resume database write gate")
    resume.add_argument("--actor", required=True)
    resume.add_argument("--confirm-resume", action="store_true")
    resume.set_defaults(handler=lambda args: _set_pause(args, False))

    opt_out = subparsers.add_parser("opt-out", help="record a user opt-out")
    opt_out.add_argument("user_id")
    opt_out.add_argument("--scope", choices=("all", "reply", "follow"), default="all")
    opt_out.add_argument("--reason", required=True)
    opt_out.set_defaults(handler=_opt_out)

    status = subparsers.add_parser("status", help="show counts and recent audit")
    status.set_defaults(handler=_status)

    serve = subparsers.add_parser("serve", help="serve the loopback approval console")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(handler=_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (
        ConfigError,
        DraftError,
        ExecutionBlocked,
        RelationshipDataError,
        StoreConflict,
        StoreError,
        XApiError,
    ) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
