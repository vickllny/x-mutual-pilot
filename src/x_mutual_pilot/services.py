"""Application services for relationship sync and post discovery."""

from __future__ import annotations

from typing import Mapping

from .drafts import DraftError
from .scoring import FollowBackScorer
from .safety import ContentSafetyFilter
from .store import Store


def _highest_id(records: list[Mapping[str, object]]) -> str | None:
    ids = [str(record.get("id", "")) for record in records]
    numeric = [value for value in ids if value.isdigit()]
    return max(numeric, key=int) if numeric else None


class RelationshipSyncService:
    def __init__(
        self,
        store: Store,
        client: object,
        scorer: FollowBackScorer,
        *,
        approval_expiry_minutes: int,
    ) -> None:
        self._store = store
        self._client = client
        self._scorer = scorer
        self._expiry = approval_expiry_minutes

    def sync(self, account_id: int, account_user_id: str) -> dict[str, object]:
        followers = self._client.followers(account_user_id)
        following = self._client.following(account_user_id)
        changes = self._store.sync_relationships(
            account_id, followers=followers, following=following
        )
        created = 0
        for user_id in changes["new_follower_ids"]:
            profile = self._store.get_profile(str(user_id))
            if profile is None:
                continue
            result = self._scorer.score(profile)
            if result["decision"] == "reject":
                continue
            self._store.create_candidate(
                account_id,
                action_type="follow",
                target_user_id=str(user_id),
                target_post_id=None,
                score=int(result["score"]),
                reasons=result["reasons"],
                risk_flags=result["riskFlags"],
                draft=None,
                explicit_intent=False,
                expires_in_minutes=self._expiry,
            )
            created += 1
        return {
            **changes,
            "new_followers": len(changes["new_follower_ids"]),
            "follow_candidates_created": created,
        }


class PostWatcher:
    def __init__(
        self,
        store: Store,
        client: object,
        draft_generator: object,
        *,
        approval_expiry_minutes: int,
        controlled_auto_enabled: bool = False,
        content_filter: ContentSafetyFilter | None = None,
    ) -> None:
        self._store = store
        self._client = client
        self._drafts = draft_generator
        self._expiry = approval_expiry_minutes
        self._controlled_auto = controlled_auto_enabled
        self._content_filter = content_filter or ContentSafetyFilter()

    def poll(
        self, account_id: int, account_user_id: str, *, limit_users: int = 100
    ) -> dict[str, int]:
        created = 0
        skipped = 0
        mutual_ids = self._store.mutual_user_ids(account_id)[:limit_users]
        for user_id in mutual_ids:
            cursor_key = f"posts:{account_id}:{user_id}"
            posts = self._client.user_posts(
                user_id, since_id=self._store.get_cursor(cursor_key)
            )
            for post in posts:
                if self._process_post(
                    account_id, post, explicit_intent=False, source="mutual_post"
                ):
                    created += 1
                else:
                    skipped += 1
            highest = _highest_id(posts)
            if highest:
                self._store.set_cursor(cursor_key, highest)

        mentions_key = f"mentions:{account_id}"
        mentions = self._client.mentions(
            account_user_id, since_id=self._store.get_cursor(mentions_key)
        )
        for post in mentions:
            if str(post.get("author_id", "")) == account_user_id:
                skipped += 1
                continue
            if self._process_post(
                account_id, post, explicit_intent=True, source="mention"
            ):
                created += 1
            else:
                skipped += 1
        highest_mention = _highest_id(mentions)
        if highest_mention:
            self._store.set_cursor(mentions_key, highest_mention)
        return {"created": created, "skipped": skipped}

    def _process_post(
        self,
        account_id: int,
        post: Mapping[str, object],
        *,
        explicit_intent: bool,
        source: str,
    ) -> bool:
        author_id = str(post.get("author_id", ""))
        text = str(post.get("text", "")).strip()
        if (
            not author_id.isdigit()
            or not text
            or bool(post.get("possibly_sensitive"))
            or not self._content_filter.assess(text).allowed
            or self._store.is_opted_out(account_id, author_id, "reply")
        ):
            return False
        if not self._store.save_post(post):
            return False

        try:
            draft_result = self._drafts.generate(text)
            draft = str(draft_result.get("draft") or "")
            risks = [
                str(flag) for flag in draft_result.get("risk_flags", [])
            ]
            reasons = [source, str(draft_result.get("provider", "unknown"))]
        except DraftError:
            draft = None
            risks = ["draft_generation_failed"]
            reasons = [source]
        if not explicit_intent:
            risks.append("no_explicit_intent")

        candidate_id = self._store.create_candidate(
            account_id,
            action_type="reply",
            target_user_id=author_id,
            target_post_id=str(post["id"]),
            score=75 if explicit_intent else 45,
            reasons=reasons,
            risk_flags=risks,
            draft=draft,
            explicit_intent=explicit_intent,
            expires_in_minutes=self._expiry,
        )
        if explicit_intent and self._controlled_auto:
            account = self._store.get_account(account_id)
            if (
                account["mode"] == "controlled-auto"
                and account["x_auto_reply_approved"]
                and not account["writes_paused"]
            ):
                self._store.approve_candidate(
                    candidate_id, actor="controlled-auto"
                )
        return True
