"""Shared builders for unit tests."""

from __future__ import annotations

from supportbot.chat import ChatService
from supportbot.memory import ConversationMemory
from supportbot.safety import ContentSafetyGuard
from supportbot.seed import seed_orders
from supportbot.storage import InMemoryTableStore, TableStore
from supportbot.tools import ToolRegistry
from tests.fakes import FakeChatClient


def make_service(llm: FakeChatClient, limit: int = 40) -> tuple[ChatService, InMemoryTableStore]:
    store = InMemoryTableStore()
    seed_orders(store)
    service = ChatService(
        llm=llm,
        memory=ConversationMemory(store, limit=limit),
        tools=ToolRegistry(store),
        safety=ContentSafetyGuard(),
    )
    return service, store


def message_text(store: TableStore, conversation_id: str) -> list[tuple[str, str]]:
    return [(str(row["role"]), str(row["content"])) for row in store.query("messages", conversation_id)]
