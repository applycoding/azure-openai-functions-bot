from supportbot.memory import ConversationMemory
from supportbot.models import Message, ToolCall
from supportbot.storage import InMemoryTableStore


def test_history_round_trips_tool_calls_and_keeps_a_safe_window():
    store = InMemoryTableStore()
    memory = ConversationMemory(store, limit=2)
    conversation_id = "conv-1"
    memory.append(conversation_id, Message(role="user", content="one"))
    memory.append(
        conversation_id,
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call-1", name="lookup_order", arguments={"order_id": "ORD-1001"})],
        ),
    )
    memory.append(
        conversation_id,
        Message(role="tool", content='{"found": true}', tool_call_id="call-1", name="lookup_order"),
    )
    memory.append(conversation_id, Message(role="assistant", content="done"))

    history = memory.history(conversation_id)
    assert [message.role for message in history] == ["assistant", "tool", "assistant"]
    assert history[0].tool_calls is not None
    assert history[0].tool_calls[0].arguments == {"order_id": "ORD-1001"}
    assert history[1].tool_call_id == "call-1"
    assert history[-1].content == "done"
