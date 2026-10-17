"""Shared chat types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResult:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class Message:
    role: str
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class ChatResult:
    conversation_id: str
    reply: str
    blocked: bool
    category: str | None
    tool_calls: list[ToolTrace]

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "reply": self.reply,
            "blocked": self.blocked,
            "category": self.category,
            "tool_calls": [
                {
                    "name": call.name,
                    "arguments": call.arguments,
                    "result": call.result,
                }
                for call in self.tool_calls
            ],
        }
