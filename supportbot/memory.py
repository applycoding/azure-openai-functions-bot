"""Conversation memory stored as table entities."""

from __future__ import annotations

import json

from supportbot.models import Message, ToolCall
from supportbot.seed import MESSAGES_TABLE
from supportbot.storage import TableStore


class ConversationMemory:
    def __init__(self, store: TableStore, limit: int = 40) -> None:
        if limit < 1:
            raise ValueError("limit must be positive")
        self._store = store
        self._limit = limit

    def history(self, conversation_id: str) -> list[Message]:
        rows = self._store.query(MESSAGES_TABLE, conversation_id)
        messages = [entity_to_message(row) for row in rows]
        return _window(messages, self._limit)

    def append(self, conversation_id: str, message: Message) -> None:
        rows = self._store.query(MESSAGES_TABLE, conversation_id)
        entity = message_to_entity(conversation_id, len(rows), message)
        self._store.upsert(MESSAGES_TABLE, entity)


def message_to_entity(conversation_id: str, index: int, message: Message) -> dict[str, object]:
    tool_calls_json = ""
    if message.tool_calls:
        tool_calls_json = json.dumps(
            [
                {"id": call.id, "name": call.name, "arguments": call.arguments}
                for call in message.tool_calls
            ]
        )
    return {
        "PartitionKey": conversation_id,
        "RowKey": f"{index:06d}",
        "role": message.role,
        "content": message.content,
        "name": message.name or "",
        "tool_call_id": message.tool_call_id or "",
        "tool_calls_json": tool_calls_json,
    }


def entity_to_message(entity: dict[str, object]) -> Message:
    raw = str(entity.get("tool_calls_json") or "")
    tool_calls: list[ToolCall] | None = None
    if raw:
        parsed = json.loads(raw)
        tool_calls = [
            ToolCall(
                id=str(item["id"]),
                name=str(item["name"]),
                arguments=dict(item.get("arguments") or {}),
            )
            for item in parsed
        ]
    tool_call_id = str(entity.get("tool_call_id") or "") or None
    name = str(entity.get("name") or "") or None
    return Message(
        role=str(entity["role"]),
        content=str(entity.get("content") or ""),
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        name=name,
    )


def _window(messages: list[Message], limit: int) -> list[Message]:
    """Keep the newest messages without starting on an orphaned tool result."""
    if len(messages) <= limit:
        window = list(messages)
    else:
        window = messages[-limit:]
        start = len(messages) - limit
        if window and window[0].role == "tool" and start > 0:
            previous = messages[start - 1]
            if previous.role == "assistant" and previous.tool_calls:
                window = [previous, *window]
    while window and window[0].role == "tool":
        window = window[1:]
    return window
