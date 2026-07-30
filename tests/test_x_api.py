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


if __name__ == "__main__":
    unittest.main()
