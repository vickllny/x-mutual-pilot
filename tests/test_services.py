from pathlib import Path
import tempfile
import unittest

from x_mutual_pilot.scoring import FollowBackScorer
from x_mutual_pilot.services import PostWatcher, RelationshipSyncService
from x_mutual_pilot.store import Store


class FakeClient:
    def __init__(self) -> None:
        self.followers_result = []
        self.following_result = []
        self.user_posts_result = {}
        self.mentions_result = []

    def followers(self, user_id: str) -> list[dict]:
        return self.followers_result

    def following(self, user_id: str) -> list[dict]:
        return self.following_result

    def user_posts(self, user_id: str, *, since_id: str | None = None) -> list[dict]:
        return self.user_posts_result.get(user_id, [])

    def mentions(self, user_id: str, *, since_id: str | None = None) -> list[dict]:
        return self.mentions_result


class FakeDraftGenerator:
    def generate(self, post_text: str) -> dict[str, object]:
        return {
            "draft": f"Draft: {post_text}",
            "risk_flags": ["ai_generated"],
            "provider": "fake",
        }


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp_dir.name) / "pilot.sqlite3")
        self.store.initialize()
        self.account_id = self.store.ensure_account(
            "999", mode="assisted", writes_paused=True, x_auto_reply_approved=False
        )
        self.client = FakeClient()

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_sync_creates_follow_candidate_only_for_new_non_rejected_follower(self) -> None:
        service = RelationshipSyncService(
            self.store,
            self.client,
            FollowBackScorer(("ai",)),
            approval_expiry_minutes=30,
        )
        self.client.followers_result = [
            {
                "id": "1",
                "description": "AI builder",
                "verified": True,
                "public_metrics": {
                    "followers_count": 100,
                    "following_count": 50,
                    "tweet_count": 20,
                },
            }
        ]
        self.client.following_result = []
        service.sync(self.account_id, "999")
        self.assertEqual(self.store.list_candidates(self.account_id), [])

        self.client.followers_result.append(
            {
                "id": "2",
                "description": "AI product maker",
                "verified": True,
                "public_metrics": {
                    "followers_count": 100,
                    "following_count": 80,
                    "tweet_count": 30,
                },
            }
        )
        result = service.sync(self.account_id, "999")

        candidates = self.store.list_candidates(self.account_id)
        self.assertEqual(result["new_followers"], 1)
        self.assertEqual(candidates[0]["action_type"], "follow")
        self.assertEqual(candidates[0]["target_user_id"], "2")

    def test_post_watcher_separates_mutual_posts_from_explicit_mentions(self) -> None:
        self.store.sync_relationships(
            self.account_id,
            followers=[{"id": "1"}],
            following=[{"id": "1"}],
        )
        self.client.user_posts_result = {
            "1": [
                {
                    "id": "100",
                    "author_id": "1",
                    "text": "Mutual post",
                    "possibly_sensitive": False,
                }
            ]
        }
        self.client.mentions_result = [
            {
                "id": "101",
                "author_id": "2",
                "text": "@pilot what do you think?",
                "possibly_sensitive": False,
            }
        ]
        watcher = PostWatcher(
            self.store,
            self.client,
            FakeDraftGenerator(),
            approval_expiry_minutes=30,
        )

        result = watcher.poll(self.account_id, "999")

        candidates = {
            candidate["target_post_id"]: candidate
            for candidate in self.store.list_candidates(self.account_id)
        }
        self.assertEqual(result["created"], 2)
        self.assertFalse(candidates["100"]["explicit_intent"])
        self.assertIn("no_explicit_intent", candidates["100"]["risk_flags"])
        self.assertTrue(candidates["101"]["explicit_intent"])

    def test_controlled_auto_only_auto_approves_explicit_mention(self) -> None:
        auto_account = self.store.ensure_account(
            "998",
            mode="controlled-auto",
            writes_paused=False,
            x_auto_reply_approved=True,
        )
        self.client.mentions_result = [
            {
                "id": "201",
                "author_id": "3",
                "text": "@pilot please reply",
                "possibly_sensitive": False,
            }
        ]
        watcher = PostWatcher(
            self.store,
            self.client,
            FakeDraftGenerator(),
            approval_expiry_minutes=30,
            controlled_auto_enabled=True,
        )

        watcher.poll(auto_account, "998")

        candidate = self.store.list_candidates(auto_account)[0]
        self.assertEqual(candidate["status"], "approved")
        self.assertEqual(candidate["approved_by"], "controlled-auto")


if __name__ == "__main__":
    unittest.main()
