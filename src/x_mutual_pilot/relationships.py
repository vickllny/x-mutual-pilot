"""Build deterministic follower, following, and mutual snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping


class RelationshipDataError(ValueError):
    """Raised when X user data cannot form a safe relationship snapshot."""


def _normalize_users(
    users: Iterable[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    for user in users:
        user_id = str(user.get("id", "")).strip()
        if not user_id.isdigit():
            raise RelationshipDataError("every user must have a numeric id")
        normalized[user_id] = {
            key: value
            for key, value in user.items()
            if key in {"id", "name", "username", "protected", "verified"}
        }
        normalized[user_id]["id"] = user_id
    return normalized


def _sort_profiles(profiles: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(profiles, key=lambda profile: (len(str(profile["id"])), profile["id"]))


def build_relationship_snapshot(
    account_user_id: str,
    followers: Iterable[Mapping[str, object]],
    following: Iterable[Mapping[str, object]],
    *,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    if not account_user_id.isdigit():
        raise RelationshipDataError("account_user_id must be numeric")
    follower_map = _normalize_users(followers)
    following_map = _normalize_users(following)
    mutual_ids = follower_map.keys() & following_map.keys()
    timestamp = generated_at or datetime.now(timezone.utc)

    mutual_profiles = []
    for user_id in mutual_ids:
        merged = dict(follower_map[user_id])
        merged.update(following_map[user_id])
        mutual_profiles.append(merged)

    return {
        "schema_version": 1,
        "account_user_id": account_user_id,
        "generated_at": timestamp.astimezone(timezone.utc).isoformat(),
        "counts": {
            "followers": len(follower_map),
            "following": len(following_map),
            "mutuals": len(mutual_ids),
        },
        "followers": _sort_profiles(follower_map.values()),
        "following": _sort_profiles(following_map.values()),
        "mutuals": _sort_profiles(mutual_profiles),
    }
