from io import BytesIO
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from x_mutual_pilot.x_api import XApiClient, XApiError


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class XApiClientTests(unittest.TestCase):
    def test_follows_pagination_and_sends_bearer_token(self) -> None:
        requests = []
        pages = [
            {"data": [{"id": "1"}], "meta": {"next_token": "next"}},
            {"data": [{"id": "2"}], "meta": {}},
        ]

        def opener(request: object, *, timeout: float) -> FakeResponse:
            requests.append((request, timeout))
            return FakeResponse(pages[len(requests) - 1])

        client = XApiClient("secret-token", opener=opener)
        users = client.followers("99")

        self.assertEqual([user["id"] for user in users], ["1", "2"])
        self.assertEqual(
            requests[0][0].get_header("Authorization"), "Bearer secret-token"
        )
        second_query = parse_qs(urlparse(requests[1][0].full_url).query)
        self.assertEqual(second_query["pagination_token"], ["next"])

    def test_stops_on_http_error_without_exposing_body(self) -> None:
        def opener(request: object, *, timeout: float) -> FakeResponse:
            raise HTTPError(
                request.full_url,
                429,
                "Too Many Requests",
                {},
                BytesIO(b'{"detail":"sensitive upstream body"}'),
            )

        client = XApiClient("secret-token", opener=opener)
        with self.assertRaises(XApiError) as raised:
            client.following("99")

        self.assertEqual(raised.exception.status, 429)
        self.assertNotIn("sensitive", str(raised.exception))

    def test_rejects_repeated_pagination_token(self) -> None:
        def opener(request: object, *, timeout: float) -> FakeResponse:
            return FakeResponse({"data": [], "meta": {"next_token": "same"}})

        client = XApiClient("secret-token", opener=opener)
        with self.assertRaisesRegex(XApiError, "repeated pagination token"):
            client.followers("99")

    def test_rejects_partial_errors_to_avoid_incomplete_snapshot(self) -> None:
        def opener(request: object, *, timeout: float) -> FakeResponse:
            return FakeResponse(
                {
                    "data": [{"id": "1"}],
                    "errors": [{"detail": "partial failure"}],
                    "meta": {},
                }
            )

        client = XApiClient("secret-token", opener=opener)
        with self.assertRaisesRegex(XApiError, "partial errors"):
            client.followers("99")

    def test_reads_user_posts_with_since_id(self) -> None:
        captured = {}

        def opener(request: object, *, timeout: float) -> FakeResponse:
            captured["url"] = request.full_url
            return FakeResponse({"data": [{"id": "10", "text": "Post"}], "meta": {}})

        client = XApiClient("read-token", opener=opener)
        posts = client.user_posts("99", since_id="9")

        query = parse_qs(urlparse(captured["url"]).query)
        self.assertEqual(posts[0]["id"], "10")
        self.assertEqual(query["since_id"], ["9"])
        self.assertEqual(query["exclude"], ["retweets,replies"])

    def test_write_methods_require_user_token_and_send_expected_payloads(self) -> None:
        requests = []

        def opener(request: object, *, timeout: float) -> FakeResponse:
            requests.append(request)
            if request.method == "GET":
                return FakeResponse({"data": {"id": "100", "text": "Post"}})
            if request.full_url.endswith("/tweets"):
                return FakeResponse({"data": {"id": "200", "text": "Reply"}})
            return FakeResponse({"data": {"following": True}})

        client = XApiClient(
            "read-token", user_access_token="user-token", opener=opener
        )
        client.get_post("100")
        client.create_reply("Reply", "100", made_with_ai=True)
        client.follow_user("99", "2")

        self.assertEqual(requests[1].method, "POST")
        self.assertEqual(
            json.loads(requests[1].data),
            {
                "text": "Reply",
                "reply": {"in_reply_to_tweet_id": "100"},
                "made_with_ai": True,
            },
        )
        self.assertEqual(
            requests[2].get_header("Authorization"), "Bearer user-token"
        )
        self.assertEqual(
            json.loads(requests[2].data), {"target_user_id": "2"}
        )


if __name__ == "__main__":
    unittest.main()
