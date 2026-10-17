"""Azure OpenAI chat client and the offline tool router.

LLM_BACKEND=azure calls Azure OpenAI through the openai SDK's AzureOpenAI
client. LLM_BACKEND=offline is a deterministic stand-in so the HTTP contract
and tools can run with no credentials. Tests use their own scripted client.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from openai import AzureOpenAI

from supportbot.models import LLMResult, Message, ToolCall
from supportbot.tools import EMAIL

logger = logging.getLogger(__name__)

_ORDER_ID = re.compile(r"ORD-\d{4}", re.IGNORECASE)
_TRACKING_WORDS = ("where", "status", "track", "tracking", "shipped", "delivery", "order", "lookup", "find")
_TICKET_WORDS = ("ticket", "complaint", "refund", "broken", "damaged", "missing", "human", "agent")


class LLMError(Exception):
    """A model call failed. The message is safe to return to the caller."""


class ChatClient(Protocol):
    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResult:
        """Return the next assistant message, which may request tool calls."""


class AzureOpenAIChatClient:
    def __init__(self, client: AzureOpenAI, deployment: str) -> None:
        self.client = client
        self._deployment = deployment

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResult:
        try:
            response = self.client.chat.completions.create(
                model=self._deployment,
                messages=[to_api_message(message) for message in messages],
                tools=tools,
                tool_choice="auto",
                temperature=0,
                max_tokens=800,
            )
        except Exception as exc:
            logger.error("Azure OpenAI request failed: %s", type(exc).__name__)
            raise LLMError("The language model request failed.") from exc
        if not response.choices:
            raise LLMError("The language model request failed.")
        return parse_assistant_message(response.choices[0].message)


class OfflineToolRouter:
    """Deterministic tool router used when Azure OpenAI is not configured."""

    def __init__(self) -> None:
        self._sequence = 0

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResult:
        del tools
        if messages and messages[-1].role == "tool":
            return LLMResult(content=_summarize_tools(messages), tool_calls=[])
        user_text = _latest_user_text(messages)
        lowered = user_text.lower()
        order_id = _order_id_in(user_text) or _order_id_in_history(messages)
        email = _email_in(user_text)
        wants_ticket = _has_word(lowered, _TICKET_WORDS)
        wants_order = _has_word(lowered, _TRACKING_WORDS)
        if wants_ticket:
            return LLMResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id=self._next_id("ticket"),
                        name="create_ticket",
                        arguments={
                            "subject": f"Issue with {order_id}" if order_id else "Support request",
                            "description": user_text,
                            "customer_email": email or "",
                            "order_id": order_id or "",
                        },
                    )
                ],
            )
        if order_id and (wants_order or _order_id_in(user_text)):
            return LLMResult(
                content=None,
                tool_calls=[
                    ToolCall(
                        id=self._next_id("lookup"),
                        name="lookup_order",
                        arguments={"order_id": order_id},
                    )
                ],
            )
        return LLMResult(
            content=(
                "I can look up an order (for example ORD-1001) or open a support ticket. "
                "Share an order id and, for a ticket, the email to reach you."
            ),
            tool_calls=[],
        )

    def _next_id(self, prefix: str) -> str:
        self._sequence += 1
        return f"offline-{prefix}-{self._sequence}"


def to_api_message(message: Message) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content,
        }
    if message.role == "assistant" and message.tool_calls:
        return {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    },
                }
                for call in message.tool_calls
            ],
        }
    return {"role": message.role, "content": message.content}


def parse_assistant_message(message: Any) -> LLMResult:
    tool_calls: list[ToolCall] = []
    for call in getattr(message, "tool_calls", None) or []:
        function = getattr(call, "function", None)
        name = getattr(function, "name", "") if function is not None else ""
        raw_arguments = getattr(function, "arguments", "") if function is not None else ""
        tool_calls.append(
            ToolCall(
                id=str(getattr(call, "id", "") or ""),
                name=str(name),
                arguments=parse_arguments(raw_arguments),
            )
        )
    content = getattr(message, "content", None)
    if content is not None:
        content = str(content)
    return LLMResult(content=content, tool_calls=tool_calls)


def parse_arguments(raw: object) -> dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _latest_user_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.role == "user" and not message.content.startswith("[blocked"):
            return message.content
    return ""


def _order_id_in(text: str) -> str | None:
    match = _ORDER_ID.search(text)
    if match is None:
        return None
    return match.group(0).upper()


def _has_word(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def _order_id_in_history(messages: list[Message]) -> str | None:
    for message in reversed(messages):
        if message.role != "user":
            continue
        found = _order_id_in(message.content)
        if found:
            return found
    return None


def _email_in(text: str) -> str | None:
    match = EMAIL.search(text)
    if match is None:
        return None
    return match.group(0)


def _summarize_tools(messages: list[Message]) -> str:
    tool_messages: list[Message] = []
    for message in reversed(messages):
        if message.role != "tool":
            break
        tool_messages.append(message)
    tool_messages.reverse()
    parts: list[str] = []
    for message in tool_messages:
        payload = _load_payload(message.content)
        parts.append(_summarize_one(message.name or "", payload))
    return " ".join(parts)


def _load_payload(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _summarize_one(name: str, payload: dict[str, Any]) -> str:
    if name == "lookup_order":
        if payload.get("found"):
            order = payload.get("order")
            if not isinstance(order, dict):
                return "I couldn't read that order."
            sentence = f"Order {order.get('order_id')} ({order.get('item')}) is {order.get('status')}."
            tracking = str(order.get("tracking_number") or "")
            carrier = str(order.get("carrier") or "")
            if tracking:
                sentence += f" Tracking {tracking}"
                if carrier:
                    sentence += f" via {carrier}"
                sentence += "."
            return sentence
        return str(payload.get("message") or "I couldn't find that order.")
    if name == "create_ticket":
        if payload.get("created"):
            ticket = payload.get("ticket")
            if not isinstance(ticket, dict):
                return "I couldn't read that ticket."
            return (
                f"Opened ticket {ticket.get('ticket_id')} ({ticket.get('status')}) "
                f"for {ticket.get('customer_email')}."
            )
        return str(payload.get("message") or "I couldn't open that ticket.")
    return str(payload.get("message") or "I couldn't use that tool.")
