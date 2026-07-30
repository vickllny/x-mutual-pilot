import unittest

from x_mutual_pilot.config import ConfigError, Settings, environment_diagnostics


class SettingsTests(unittest.TestCase):
    def test_safe_defaults(self) -> None:
        settings = Settings.from_environment(
            {"X_BEARER_TOKEN": "secret", "X_ACCOUNT_USER_ID": "123"}
        )

        self.assertEqual(settings.mode, "observe")
        self.assertTrue(settings.writes_paused)

    def test_rejects_invalid_user_id(self) -> None:
        with self.assertRaisesRegex(ConfigError, "1 to 19 digits"):
            Settings.from_environment(
                {"X_BEARER_TOKEN": "secret", "X_ACCOUNT_USER_ID": "name"}
            )

    def test_rejects_invalid_mode(self) -> None:
        with self.assertRaisesRegex(ConfigError, "X_AGENT_MODE"):
            Settings.from_environment(
                {
                    "X_BEARER_TOKEN": "secret",
                    "X_ACCOUNT_USER_ID": "123",
                    "X_AGENT_MODE": "automatic",
                }
            )

    def test_diagnostics_do_not_expose_token(self) -> None:
        diagnostics = environment_diagnostics(
            {"X_BEARER_TOKEN": "top-secret", "X_ACCOUNT_USER_ID": "123"}
        )

        self.assertTrue(diagnostics["ready"])
        self.assertNotIn("top-secret", str(diagnostics))

    def test_controlled_auto_requires_mode_and_x_approval(self) -> None:
        with self.assertRaisesRegex(ConfigError, "controlled-auto"):
            Settings.from_environment(
                {
                    "X_BEARER_TOKEN": "secret",
                    "X_ACCOUNT_USER_ID": "123",
                    "X_CONTROLLED_AUTO_ENABLED": "true",
                    "X_AI_REPLY_APPROVED": "true",
                }
            )
        with self.assertRaisesRegex(ConfigError, "X_AI_REPLY_APPROVED"):
            Settings.from_environment(
                {
                    "X_BEARER_TOKEN": "secret",
                    "X_ACCOUNT_USER_ID": "123",
                    "X_AGENT_MODE": "controlled-auto",
                    "X_CONTROLLED_AUTO_ENABLED": "true",
                }
            )


if __name__ == "__main__":
    unittest.main()
