import unittest

from x_mutual_pilot.scoring import FollowBackScorer


class FollowBackScorerTests(unittest.TestCase):
    def test_recommends_relevant_established_profile(self) -> None:
        result = FollowBackScorer(("ai", "product")).score(
            {
                "id": "1",
                "description": "Building AI product tools",
                "verified": True,
                "public_metrics": {
                    "followers_count": 250,
                    "following_count": 180,
                    "tweet_count": 90,
                },
            }
        )

        self.assertEqual(result["decision"], "recommend_follow")
        self.assertGreaterEqual(result["score"], 65)
        self.assertIn("topic_match", result["reasons"])

    def test_rejects_bulk_following_empty_profile(self) -> None:
        result = FollowBackScorer(("ai",)).score(
            {
                "id": "2",
                "description": "",
                "public_metrics": {
                    "followers_count": 2,
                    "following_count": 1000,
                    "tweet_count": 1,
                },
            }
        )

        self.assertEqual(result["decision"], "reject")
        self.assertIn("bulk_following_pattern", result["riskFlags"])


if __name__ == "__main__":
    unittest.main()
