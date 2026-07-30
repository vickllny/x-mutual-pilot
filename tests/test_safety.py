import unittest

from x_mutual_pilot.safety import ContentSafetyFilter


class ContentSafetyTests(unittest.TestCase):
    def test_allows_ordinary_product_discussion(self) -> None:
        result = ContentSafetyFilter().assess("A thoughtful product update")
        self.assertTrue(result.allowed)

    def test_blocks_sensitive_personal_and_configured_terms(self) -> None:
        cases = [
            ("email me at person@example.com", "possible_personal_data"),
            ("send nudes", "sensitive_content"),
            ("secret campaign", "configured_blocked_term"),
        ]
        filter_with_term = ContentSafetyFilter(("secret campaign",))
        for text, expected in cases:
            with self.subTest(text=text):
                result = filter_with_term.assess(text)
                self.assertFalse(result.allowed)
                self.assertIn(expected, result.risk_flags)


if __name__ == "__main__":
    unittest.main()
