from pathlib import Path
import tempfile
import unittest

from x_mutual_pilot.store import Store, StoreConflict


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "pilot.sqlite3"
        self.store = Store(self.db_path)
        self.store.initialize()
        self.account_id = self.store.ensure_account(
            "999", mode="assisted", writes_paused=True, x_auto_reply_approved=False
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_first_relationship_sync_is_baseline_then_detects_new_follower(self) -> None:
        baseline = self.store.sync_relationships(
            self.account_id,
            followers=[{"id": "1", "username": "one"}],
            following=[{"id": "1", "username": "one"}],
        )
        changed = self.store.sync_relationships(
            self.account_id,
            followers=[
                {"id": "1", "username": "one"},
                {"id": "2", "username": "two"},
            ],
            following=[{"id": "1", "username": "one"}],
        )

        self.assertEqual(baseline["new_follower_ids"], [])
        self.assertEqual(changed["new_follower_ids"], ["2"])
        self.assertEqual(self.store.mutual_user_ids(self.account_id), ["1"])

    def test_candidate_dedupe_and_approval_preserve_original_draft(self) -> None:
        candidate_id = self.store.create_candidate(
            self.account_id,
            action_type="reply",
            target_user_id="1",
            target_post_id="100",
            score=80,
            reasons=["relevant"],
            risk_flags=[],
            draft="Original",
            explicit_intent=True,
            expires_in_minutes=30,
        )
        duplicate_id = self.store.create_candidate(
            self.account_id,
            action_type="reply",
            target_user_id="1",
            target_post_id="100",
            score=90,
            reasons=["duplicate"],
            risk_flags=[],
            draft="Replacement",
            explicit_intent=True,
            expires_in_minutes=30,
        )
        self.store.approve_candidate(
            candidate_id, actor="reviewer", edited_draft="Edited"
        )
        candidate = self.store.get_candidate(candidate_id)

        self.assertEqual(candidate_id, duplicate_id)
        self.assertEqual(candidate["original_draft"], "Original")
        self.assertEqual(candidate["draft"], "Edited")
        self.assertEqual(candidate["status"], "approved")
        with self.assertRaises(StoreConflict):
            self.store.approve_candidate(candidate_id, actor="reviewer")

    def test_pause_and_opt_out_are_persistent(self) -> None:
        self.store.set_writes_paused(self.account_id, False, actor="owner")
        self.store.add_opt_out(self.account_id, "2", "all", "requested")

        account = self.store.get_account(self.account_id)
        self.assertFalse(account["writes_paused"])
        self.assertTrue(self.store.is_opted_out(self.account_id, "2", "reply"))

    def test_snooze_returns_to_pending_when_due(self) -> None:
        candidate_id = self.store.create_candidate(
            self.account_id,
            action_type="follow",
            target_user_id="3",
            target_post_id=None,
            score=60,
            reasons=[],
            risk_flags=[],
            draft=None,
            explicit_intent=False,
            expires_in_minutes=30,
        )
        self.store.snooze_candidate(candidate_id, actor="reviewer", minutes=5)
        candidate = self.store.get_candidate(candidate_id)
        self.assertEqual(candidate["status"], "snoozed")

        from datetime import datetime, timedelta, timezone

        self.store.refresh_candidate_states(
            now=datetime.now(timezone.utc) + timedelta(minutes=6)
        )
        self.assertEqual(
            self.store.get_candidate(candidate_id)["status"], "pending"
        )


if __name__ == "__main__":
    unittest.main()
