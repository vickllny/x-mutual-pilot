from pathlib import Path
import tempfile
import unittest

from x_mutual_pilot.store import Store
from x_mutual_pilot.web import DashboardApp


class DashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp_dir.name) / "pilot.sqlite3")
        self.store.initialize()
        self.account_id = self.store.ensure_account(
            "999", mode="assisted", writes_paused=True, x_auto_reply_approved=False
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_dashboard_renders_queue_metrics_and_safety_state(self) -> None:
        self.store.create_candidate(
            self.account_id,
            action_type="reply",
            target_user_id="2",
            target_post_id="100",
            score=70,
            reasons=["mention"],
            risk_flags=[],
            draft="Thanks",
            explicit_intent=True,
            expires_in_minutes=30,
        )
        app = DashboardApp(self.store, self.account_id, csrf_token="test-csrf")

        html = app.render_dashboard()

        self.assertIn('name="viewport"', html)
        self.assertIn("Writes paused", html)
        self.assertIn("Thanks", html)
        self.assertIn('value="test-csrf"', html)
        self.assertIn("Approve", html)
        self.assertIn("Snooze", html)

    def test_dashboard_actions_require_csrf(self) -> None:
        app = DashboardApp(self.store, self.account_id, csrf_token="test-csrf")
        with self.assertRaisesRegex(ValueError, "CSRF"):
            app.handle_action("/pause", {"csrf": ["wrong"], "actor": ["owner"]})


if __name__ == "__main__":
    unittest.main()
