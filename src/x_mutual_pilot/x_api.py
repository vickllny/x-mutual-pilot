"""X API v2 adapter with explicit read and user-context write paths."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class XApiError(RuntimeError):
    """Raised for safe-to-display X API failures."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class XApiClient:
    USER_FIELDS = (
        "id,name,username,description,protected,verified,public_metrics"
    )

    def __init__(
        self,
        bearer_token: str,
        *,
        user_access_token: str | None = None,
        base_url: str = "https://api.x.com/2",
        timeout_seconds: float = 20.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self._bearer_token = bearer_token
        self._user_access_token = user_access_token
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def followers(self, user_id: str) -> list[dict[str, object]]:
        return list(self._iter_users(f"/users/{user_id}/followers"))

    def following(self, user_id: str) -> list[dict[str, object]]:
        return list(self._iter_users(f"/users/{user_id}/following"))

    def user_posts(
        self, user_id: str, *, since_id: str | None = None
    ) -> list[dict[str, object]]:
        params = {
            "max_results": "100",
            "exclude": "retweets,replies",
            "tweet.fields": (
                "id,text,author_id,conversation_id,created_at,lang,"
                "possibly_sensitive,referenced_tweets"
            ),
        }
        if since_id:
            params["since_id"] = since_id
        return self._get_records(f"/users/{user_id}/tweets", params)

    def mentions(
        self, user_id: str, *, since_id: str | None = None
    ) -> list[dict[str, object]]:
        params = {
            "max_results": "100",
            "tweet.fields": (
                "id,text,author_id,conversation_id,created_at,lang,"
                "possibly_sensitive,referenced_tweets"
            ),
        }
        if since_id:
            params["since_id"] = since_id
        return self._get_records(f"/users/{user_id}/mentions", params)

    def get_post(self, post_id: str) -> dict[str, object]:
        payload = self._request_json(
            "GET",
            f"/tweets/{post_id}",
            params={
                "tweet.fields": (
                    "id,text,author_id,conversation_id,created_at,lang,"
                    "possibly_sensitive"
                )
            },
        )
        self._raise_partial_errors(payload)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise XApiError("X API response field 'data' must be an object")
        return data

    def create_reply(
        self, text: str, post_id: str, *, made_with_ai: bool = False
    ) -> dict[str, object]:
        body: dict[str, object] = {
            "text": text,
            "reply": {"in_reply_to_tweet_id": post_id},
        }
        if made_with_ai:
            body["made_with_ai"] = True
        payload = self._request_json(
            "POST",
            "/tweets",
            body=body,
            use_user_token=True,
        )
        self._raise_partial_errors(payload)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise XApiError("X API response field 'data' must be an object")
        return data

    def follow_user(
        self, source_user_id: str, target_user_id: str
    ) -> dict[str, object]:
        payload = self._request_json(
            "POST",
            f"/users/{source_user_id}/following",
            body={"target_user_id": target_user_id},
            use_user_token=True,
        )
        self._raise_partial_errors(payload)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise XApiError("X API response field 'data' must be an object")
        return data

    @staticmethod
    def _raise_partial_errors(payload: dict[str, object]) -> None:
        if payload.get("errors"):
            raise XApiError("X API returned one or more partial errors")

    def _get_records(
        self, path: str, base_params: dict[str, str]
    ) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            params = dict(base_params)
            if token:
                params["pagination_token"] = token
            payload = self._request_json("GET", path, params=params)
            self._raise_partial_errors(payload)
            data = payload.get("data", [])
            if not isinstance(data, list) or not all(
                isinstance(item, dict) for item in data
            ):
                raise XApiError("X API response field 'data' must be a list")
            records.extend(data)
            meta = payload.get("meta", {})
            if not isinstance(meta, dict) or meta.get("next_token") is None:
                return records
            token = str(meta["next_token"])
            if token in seen_tokens:
                raise XApiError("X API returned a repeated pagination token")
            seen_tokens.add(token)

    def _iter_users(self, path: str) -> Iterator[dict[str, object]]:
        token: str | None = None
        seen_tokens: set[str] = set()

        while True:
            params = {
                "max_results": "1000",
                "user.fields": self.USER_FIELDS,
            }
            if token is not None:
                params["pagination_token"] = token

            payload = self._request_json("GET", path, params=params)
            self._raise_partial_errors(payload)
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise XApiError("X API response field 'data' must be a list")
            for user in data:
                if not isinstance(user, dict):
                    raise XApiError("X API returned an invalid user record")
                yield user

            meta = payload.get("meta", {})
            if not isinstance(meta, dict):
                raise XApiError("X API response field 'meta' must be an object")
            next_token = meta.get("next_token")
            if next_token is None:
                return
            token = str(next_token)
            if token in seen_tokens:
                raise XApiError("X API returned a repeated pagination token")
            seen_tokens.add(token)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, object] | None = None,
        use_user_token: bool = False,
    ) -> dict[str, object]:
        query = f"?{urlencode(params)}" if params else ""
        url = f"{self._base_url}{path}{query}"
        token = self._user_access_token if use_user_token else self._bearer_token
        if not token:
            raise XApiError("X user access token is required for write operations")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "x-mutual-pilot/0.2",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        request = Request(
            url,
            method=method,
            data=data,
            headers=headers,
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except HTTPError as error:
            raise XApiError(
                f"X API request failed with HTTP {error.code}", status=error.code
            ) from error
        except URLError as error:
            raise XApiError("X API request could not reach the server") from error

        try:
            payload = json.loads(body)
        except (JSONDecodeError, UnicodeDecodeError) as error:
            raise XApiError("X API returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise XApiError("X API response must be a JSON object")
        return payload
