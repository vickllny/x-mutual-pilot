"""Command-line entry point for the read-only MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import ConfigError, Settings, environment_diagnostics
from .relationships import RelationshipDataError, build_relationship_snapshot
from .x_api import XApiClient, XApiError


def _write_json(payload: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def _doctor(_: argparse.Namespace) -> int:
    diagnostics = environment_diagnostics()
    _write_json(diagnostics, None)
    return 0 if diagnostics["ready"] else 2


def _sync_relationships(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    client = XApiClient(
        settings.bearer_token,
        base_url=settings.api_base_url,
        timeout_seconds=args.timeout,
    )
    snapshot = build_relationship_snapshot(
        settings.account_user_id,
        client.followers(settings.account_user_id),
        client.following(settings.account_user_id),
    )
    snapshot["runtime"] = {
        "mode": settings.mode,
        "writes_paused": settings.writes_paused,
        "read_only": True,
    }
    _write_json(snapshot, args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="x-mutual-pilot",
        description="Inspect X mutual relationships without write operations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="validate secret-safe configuration")
    doctor.set_defaults(handler=_doctor)

    sync = subparsers.add_parser(
        "sync-relationships",
        help="read followers/following and output a mutual snapshot",
    )
    sync.add_argument(
        "--output",
        type=Path,
        help="write JSON to this path instead of stdout",
    )
    sync.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="per-request timeout in seconds (default: 20)",
    )
    sync.set_defaults(handler=_sync_relationships)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (ConfigError, RelationshipDataError, XApiError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
