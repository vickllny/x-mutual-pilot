"""Conservative source and draft text safety checks."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


DEFAULT_SENSITIVE_PATTERNS = (
    re.compile(r"\b(kill yourself|self[- ]?harm|porn|nudes?)\b", re.IGNORECASE),
    re.compile(r"(自杀|自残|色情|裸照)"),
)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")


@dataclass(frozen=True)
class SafetyAssessment:
    allowed: bool
    risk_flags: tuple[str, ...]


class ContentSafetyFilter:
    def __init__(self, blocked_terms: Iterable[str] = ()) -> None:
        self._blocked_terms = tuple(
            term.strip().lower() for term in blocked_terms if term.strip()
        )

    def assess(self, text: str) -> SafetyAssessment:
        normalized = " ".join(text.split())
        flags: list[str] = []
        lowered = normalized.lower()
        if not normalized:
            flags.append("empty_content")
        if any(term in lowered for term in self._blocked_terms):
            flags.append("configured_blocked_term")
        if any(pattern.search(normalized) for pattern in DEFAULT_SENSITIVE_PATTERNS):
            flags.append("sensitive_content")
        if EMAIL_PATTERN.search(normalized) or PHONE_PATTERN.search(normalized):
            flags.append("possible_personal_data")
        return SafetyAssessment(allowed=not flags, risk_flags=tuple(flags))
