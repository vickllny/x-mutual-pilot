from pathlib import Path
import tempfile
import unittest

from x_mutual_pilot.executor import ActionExecutor, ExecutionBlocked
from x_mutual_pilot.policy import PolicyLimits
from x_mutual_pilot.store import Store
from x_mutual_pilot.x_api import XApiError


class FakeWriteClient:
    def __init__(self) -> None:
        self.follow_calls = []
        self.reply_calls = []

    def follow_user(self, source_user_id: str, target_user_id: str) -> dict:
        self.follow_calls.append((source_user_id, target_user_id))
        return {"following": True}

    def get_post(self, post_id: str) -> dict:
        return {"id": post_id, "text": "still exists"}

    def create_reply(
        self, text: str, post_id: str, *, made_with_ai: bool = False
    ) -> dict:
        self.reply_calls.append((text, post_id, made_with_ai))
        return {"id": "result-1", "text": text}


class ExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp_dir.name) / "pilot.sqlite3")
        self.store.initialize()
        self.account_id = self.store.ensure_account(
            "999", mode="assisted", writes_paused=False, x_auto_reply_approved=True
        )
        self.client = FakeWriteClient()

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_executes_approved_follow_once(self) -> None:
        candidate_id = self.store.create_candidate(
            self.account_id,
            action_type="follow",
            target_user_id="2",
            target_post_id=None,
            score=90,
            reasons=["topic_match"],
            risk_flags=[],
            draft=None,
            explicit_intent=False,
            expires_in_minutes=30,
        )
        self.store.approve_candidate(candidate_id, actor="reviewer")
        executor = ActionExecutor(
            self.store,
            self.client,
            environment_writes_paused=False,
            limits=PolicyLimits(),
        )

        result = executor.execute(candidate_id, actor="operator")

        self.assertEqual(result["result_status"], "succeeded")
        self.assertEqual(self.client.follow_calls, [("999", "2")])
        with self.assertRaises(ExecutionBlocked):
            executor.execute(candidate_id, actor="operator")

    def test_blocks_reply_without_explicit_intent_before_network(self) -> None:
        candidate_id = self.store.create_candidate(
            self.account_id,
            action_type="reply",
            target_user_id="2",
            target_post_id="100",
            score=60,
            reasons=[],
            risk_flags=[],
            draft="Reply",
            explicit_intent=False,
            expires_in_minutes=30,
        )
        self.store.approve_candidate(candidate_id, actor="reviewer")
        executor = ActionExecutor(
            self.store,
            self.client,
            environment_writes_paused=False,
            limits=PolicyLimits(),
        )

        with self.assertRaisesRegex(ExecutionBlocked, "explicit_intent_required"):
            executor.execute(candidate_id, actor="operator")
        self.assertEqual(self.client.reply_calls, [])

    def test_auth_failure_persistently_pauses_writes(self) -> None:
        candidate_id = self.store.create_candidate(
            self.account_id,
            action_type="follow",
            target_user_id="4",
            target_post_id=None,
            score=90,
            reasons=[],
            risk_flags=[],
            draft=None,
            explicit_intent=False,
            expires_in_minutes=30,
        )
        self.store.approve_candidate(candidate_id, actor="reviewer")

        def fail_follow(source_user_id: str, target_user_id: str) -> dict:
            raise XApiError("forbidden", status=403)

        self.client.follow_user = fail_follow
        executor = ActionExecutor(
            self.store,
            self.client,
            environment_writes_paused=False,
            limits=PolicyLimits(),
        )

        with self.assertRaises(XApiError):
            executor.execute(candidate_id, actor="operator")
        self.assertTrue(self.store.get_account(self.account_id)["writes_paused"])
        alerts = self.store.active_alerts(self.account_id)
        self.assertTrue(
            any(alert["code"] == "x_api_403" for alert in alerts)
        )


if __name__ == "__main__":
    unittest.main()
