"""In-process content checks for the support assistant.

The filter is a portfolio-demo guardrail. A deployed Azure OpenAI model still
applies the service's own content filters. This module does not call Azure AI
Content Safety and does not claim to score or benchmark safety.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SafetyVerdict:
    allowed: bool
    category: str | None = None
    refusal: str | None = None


_REFUSALS = {
    "prompt_injection": "I can only help with order status and support tickets.",
    "secrets": "I can't share secrets, credentials, or internal configuration.",
    "abuse": "I can't help with that. I can look up an order or open a support ticket.",
    "sensitive_data": (
        "Please don't send card numbers or government IDs. "
        "I can look up an order by order id or open a ticket."
    ),
    "secret_leak": (
        "I can't show that response because it looked like a secret. "
        "Try asking about an order or a ticket."
    ),
}

_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _blocked(category: str) -> SafetyVerdict:
    return SafetyVerdict(allowed=False, category=category, refusal=_REFUSALS[category])


class ContentSafetyGuard:
    def __init__(self) -> None:
        self._input_rules: tuple[tuple[str, re.Pattern[str]], ...] = (
            (
                "prompt_injection",
                re.compile(
                    r"ignore (all |the )?(previous|prior) (instructions|rules)|"
                    r"reveal (the )?(system |developer )?prompt|"
                    r"\bjailbreak\b|"
                    r"you are now|"
                    r"disregard (the )?(system|developer)",
                    re.IGNORECASE,
                ),
            ),
            (
                "secrets",
                re.compile(
                    r"\b(api[_ -]?key|accountkey|connection string|client secret)\b|"
                    r"\bprint (the )?(env|environment|secrets)\b|"
                    r"\b(key vault secrets?|managed identity credential)\b",
                    re.IGNORECASE,
                ),
            ),
            ("sensitive_data", _SSN),
            ("sensitive_data", _CARD),
            (
                "abuse",
                re.compile(
                    r"\b(how to|how do i)\b.{0,40}\b(make|build)\b.{0,30}\b(bomb|explosive)s?\b|"
                    r"\b(kill|hurt|attack)\b.{0,40}\b(agent|support staff|yourself)\b",
                    re.IGNORECASE,
                ),
            ),
        )
        self._output_rules: tuple[tuple[str, re.Pattern[str]], ...] = (
            (
                "secret_leak",
                re.compile(
                    r"\b(api[_ -]?key|accountkey|client secret)\b\s*[:=]\s*\S{6,}|"
                    r"DefaultEndpointsProtocol=|"
                    r"AccountKey=",
                    re.IGNORECASE,
                ),
            ),
            ("sensitive_data", _SSN),
            ("sensitive_data", _CARD),
        )

    def screen_input(self, text: str) -> SafetyVerdict:
        return self._screen(text, self._input_rules)

    def screen_output(self, text: str) -> SafetyVerdict:
        return self._screen(text, self._output_rules)

    def _screen(
        self,
        text: str,
        rules: tuple[tuple[str, re.Pattern[str]], ...],
    ) -> SafetyVerdict:
        for category, pattern in rules:
            if pattern.search(text):
                return _blocked(category)
        return SafetyVerdict(allowed=True)
