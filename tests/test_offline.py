from supportbot.factory import build_chat_service


def _service(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "offline")
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    monkeypatch.setenv("SEED_SAMPLE_DATA", "true")
    monkeypatch.delenv("KEY_VAULT_URL", raising=False)
    return build_chat_service()


def test_offline_lookup_remembers_the_order(monkeypatch):
    service = _service(monkeypatch)
    first = service.handle(None, "Where is order ORD-1001?")
    assert first.blocked is False
    assert first.tool_calls[0].name == "lookup_order"
    assert first.tool_calls[0].result["order"]["status"] == "shipped"
    assert "CF1001001" in first.reply

    follow_up = service.handle(first.conversation_id, "What is the tracking number?")
    assert follow_up.tool_calls[0].name == "lookup_order"
    assert "CF1001001" in follow_up.reply


def test_offline_missing_order(monkeypatch):
    service = _service(monkeypatch)
    result = service.handle(None, "Where is order ORD-9999?")
    assert "ORD-9999" in result.reply
    assert result.tool_calls[0].result["found"] is False


def test_offline_opens_a_ticket(monkeypatch):
    service = _service(monkeypatch)
    result = service.handle(
        None,
        "Please open a ticket about a damaged item on ORD-1003. My email is sam@example.com",
    )
    assert result.tool_calls[0].name == "create_ticket"
    assert result.tool_calls[0].result["created"] is True
    assert "sam@example.com" in result.reply
    assert "TCK-" in result.reply


def test_offline_asks_for_an_order_or_a_ticket(monkeypatch):
    service = _service(monkeypatch)
    result = service.handle(None, "Hello")
    assert result.tool_calls == []
    assert "ORD-1001" in result.reply
