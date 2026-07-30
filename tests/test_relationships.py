from datetime import datetime, timezone
import unittest

from x_mutual_pilot.relationships import (
    RelationshipDataError,
    build_relationship_snapshot,
)


class RelationshipSnapshotTests(unittest.TestCase):
    def test_calculates_mutuals_and_deduplicates_profiles(self) -> None:
        snapshot = build_relationship_snapshot(
            "999",
            [
                {"id": "2", "username": "two"},
                {"id": "1", "username": "old"},
                {"id": "1", "username": "one"},
            ],
            [
                {"id": "1", "username": "one", "verified": True},
                {"id": "3", "username": "three"},
            ],
            generated_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(
            snapshot["counts"], {"followers": 2, "following": 2, "mutuals": 1}
        )
        self.assertEqual([user["id"] for user in snapshot["mutuals"]], ["1"])
        self.assertTrue(snapshot["mutuals"][0]["verified"])
        self.assertEqual(snapshot["generated_at"], "2026-07-30T00:00:00+00:00")

    def test_rejects_missing_numeric_id(self) -> None:
        with self.assertRaisesRegex(RelationshipDataError, "numeric id"):
            build_relationship_snapshot("999", [{"username": "missing"}], [])

    def test_rejects_invalid_account_id(self) -> None:
        with self.assertRaisesRegex(RelationshipDataError, "account_user_id"):
            build_relationship_snapshot("account-name", [], [])


if __name__ == "__main__":
    unittest.main()
