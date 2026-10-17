"""HTTP request handling shared by the Functions host and the local server."""

from __future__ import annotations

from typing import Any

from supportbot.chat import ChatService
from supportbot.config import Settings, load_settings
from supportbot.llm import LLMError


def handle_health(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    current = load_settings() if settings is None else settings
    return 200, {
        "status": "ok",
        "service": "support-assistant",
        "llm_backend": current.llm_backend,
        "storage_backend": current.storage_backend,
    }


def handle_chat(service: ChatService, body: object) -> tuple[int, dict[str, Any]]:
    if not isinstance(body, dict):
        return 400, {"error": "JSON object body is required."}
    message = body.get("message")
    if not isinstance(message, str) or not message.strip():
        return 400, {"error": "message is required."}
    if "conversation_id" in body:
        conversation_id = body.get("conversation_id")
    else:
        conversation_id = body.get("conversationId")
    if conversation_id is not None and not isinstance(conversation_id, str):
        return 400, {"error": "conversation_id must be a string."}
    try:
        result = service.handle(conversation_id if isinstance(conversation_id, str) else None, message)
    except ValueError as exc:
        return 400, {"error": str(exc)}
    except LLMError as exc:
        return 502, {"error": str(exc)}
    return 200, result.to_dict()
