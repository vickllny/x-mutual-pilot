from datetime import datetime, timedelta, timezone
import unittest

from x_mutual_pilot.policy import PolicyInput, PolicyLimits, evaluate_execution


NOW = datetime(2026, 7, 30, tzinfo=timezone.utc)


def valid_input(**overrides: object) -> PolicyInput:
    values = {
        "action_type": "reply",
        "status": "approved",
        "expires_at": NOW + timedelta(minutes=30),
        "explicit_intent": True,
        "risk_flags": (),
        "mode": "assisted",
        "writes_paused": False,
        "environment_writes_paused": False,
        "x_auto_reply_approved": True,
        "opted_out": False,
        "duplicate_execution": False,
        "actions_last_hour": 0,
        "actions_today": 0,
        "user_in_cooldown": False,
    }
    values.update(overrides)
    return PolicyInput(**values)


class PolicyTests(unittest.TestCase):
    def test_allows_approved_reply_with_intent_and_permission(self) -> None:
        decision = evaluate_execution(valid_input(), PolicyLimits(), now=NOW)
        self.assertTrue(decision.allowed)

    def test_observe_pause_and_expiry_are_hard_blocks(self) -> None:
        cases = [
            valid_input(mode="observe"),
            valid_input(writes_paused=True),
            valid_input(environment_writes_paused=True),
            valid_input(expires_at=NOW - timedelta(seconds=1)),
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertFalse(
                    evaluate_execution(case, PolicyLimits(), now=NOW).allowed
                )

    def test_reply_requires_explicit_intent(self) -> None:
        decision = evaluate_execution(
            valid_input(explicit_intent=False), PolicyLimits(), now=NOW
        )
        self.assertIn("explicit_intent_required", decision.reasons)

    def test_ai_reply_requires_x_written_approval(self) -> None:
        decision = evaluate_execution(
            valid_input(
                risk_flags=("ai_generated",), x_auto_reply_approved=False
            ),
            PolicyLimits(),
            now=NOW,
        )
        self.assertIn("x_ai_reply_approval_required", decision.reasons)

    def test_limits_duplicates_opt_out_and_cooldown_block(self) -> None:
        decision = evaluate_execution(
            valid_input(
                opted_out=True,
                duplicate_execution=True,
                actions_last_hour=5,
                actions_today=20,
                user_in_cooldown=True,
            ),
            PolicyLimits(max_actions_per_hour=5, max_replies_per_day=20),
            now=NOW,
        )
        self.assertFalse(decision.allowed)
        self.assertGreaterEqual(len(decision.reasons), 5)


if __name__ == "__main__":
    unittest.main()
