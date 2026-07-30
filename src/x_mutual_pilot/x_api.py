"""Minimal read-only X API v2 client."""

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
    USER_FIELDS = "id,name,username,protected,verified"

    def __init__(
        self,
        bearer_token: str,
        *,
        base_url: str = "https://api.x.com/2",
        timeout_seconds: float = 20.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self._bearer_token = bearer_token
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def followers(self, user_id: str) -> list[dict[str, object]]:
        return list(self._iter_users(f"/users/{user_id}/followers"))

    def following(self, user_id: str) -> list[dict[str, object]]:
        return list(self._iter_users(f"/users/{user_id}/following"))

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

            payload = self._get_json(path, params)
            errors = payload.get("errors")
            if errors:
                raise XApiError("X API returned one or more partial errors")
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

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, object]:
        url = f"{self._base_url}{path}?{urlencode(params)}"
        request = Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self._bearer_token}",
                "Accept": "application/json",
                "User-Agent": "x-mutual-pilot/0.1",
            },
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
