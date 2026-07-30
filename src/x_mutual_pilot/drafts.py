"""Local and optional OpenAI reply draft generation."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .safety import ContentSafetyFilter


class DraftError(RuntimeError):
    """Raised when a safe draft cannot be produced."""


def _validate_draft(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise DraftError("draft is empty")
    if len(cleaned) > 280:
        raise DraftError("draft exceeds 280 characters")
    if "http://" in cleaned.lower() or "https://" in cleaned.lower():
        raise DraftError("draft must not add links")
    assessment = ContentSafetyFilter().assess(cleaned)
    if not assessment.allowed:
        raise DraftError(
            "draft failed safety checks: " + ", ".join(assessment.risk_flags)
        )
    return cleaned


class LocalDraftGenerator:
    def generate(self, post_text: str) -> dict[str, object]:
        contains_han = any("\u4e00" <= char <= "\u9fff" for char in post_text)
        draft = (
            "感谢分享，这个观点很有启发。"
            if contains_han
            else "Thanks for sharing—this is a thoughtful point."
        )
        return {
            "draft": draft,
            "alternative": None,
            "language": "zh" if contains_han else "en",
            "reason": "safe_local_fallback",
            "risk_flags": [],
            "provider": "local",
        }


class OpenAIDraftGenerator:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-5.6-luna",
        timeout_seconds: float = 30.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._opener = opener

    def generate(self, post_text: str) -> dict[str, object]:
        assessment = ContentSafetyFilter().assess(post_text)
        if not assessment.allowed:
            raise DraftError(
                "source post failed safety checks: "
                + ", ".join(assessment.risk_flags)
            )
        payload = {
            "model": self._model,
            "reasoning": {"effort": "none"},
            "store": False,
            "instructions": (
                "Draft one natural X reply in the source post's language. "
                "Preserve facts; do not invent claims, links, hashtags, marketing, "
                "or controversy. Keep it under 240 characters. Return only the reply."
            ),
            "input": post_text[:4000],
        }
        request = Request(
            "https://api.openai.com/v1/responses",
            method="POST",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "x-mutual-pilot/0.2",
            },
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                body = response.read()
        except HTTPError as error:
            raise DraftError(f"OpenAI request failed with HTTP {error.code}") from error
        except URLError as error:
            raise DraftError("OpenAI request could not reach the server") from error
        try:
            data = json.loads(body)
        except (JSONDecodeError, UnicodeDecodeError) as error:
            raise DraftError("OpenAI returned invalid JSON") from error

        texts: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    texts.append(str(content.get("text", "")))
        draft = _validate_draft(" ".join(texts))
        return {
            "draft": draft,
            "alternative": None,
            "language": "auto",
            "reason": "openai_responses",
            "risk_flags": ["ai_generated"],
            "provider": f"openai:{self._model}",
        }
