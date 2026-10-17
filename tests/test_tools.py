from supportbot.seed import seed_orders
from supportbot.storage import InMemoryTableStore
from supportbot.tools import TOOL_DEFINITIONS, ToolRegistry


def _registry() -> tuple[ToolRegistry, InMemoryTableStore]:
    store = InMemoryTableStore()
    seed_orders(store)
    return ToolRegistry(store), store


def test_tool_definitions_cover_orders_and_tickets():
    names = [item["function"]["name"] for item in TOOL_DEFINITIONS]
    assert names == ["lookup_order", "create_ticket"]


def test_lookup_normalizes_id_and_reports_missing_orders():
    tools, _store = _registry()
    found = tools.execute("lookup_order", {"order_id": "ord-1001"})
    missing = tools.execute("lookup_order", {"order_id": "ORD-9999"})
    invalid = tools.execute("lookup_order", {"order_id": "1001"})
    assert found["found"] is True
    assert found["order"]["status"] == "shipped"
    assert found["order"]["item"] == "Wireless headphones"
    assert missing["found"] is False
    assert invalid["found"] is False


def test_create_ticket_persists_an_open_ticket():
    tools, store = _registry()
    result = tools.execute(
        "create_ticket",
        {
            "subject": "Damaged dock",
            "description": "The USB-C dock arrived cracked.",
            "customer_email": "sam@example.com",
            "order_id": "ord-1003",
        },
    )
    assert result["created"] is True
    ticket = result["ticket"]
    stored = store.get("tickets", "ticket", ticket["ticket_id"])
    assert stored is not None
    assert stored["status"] == "open"
    assert stored["order_id"] == "ORD-1003"
    assert stored["customer_email"] == "sam@example.com"
    assert "T" in stored["created_at"]


def test_create_ticket_requires_a_real_email():
    tools, store = _registry()
    result = tools.execute(
        "create_ticket",
        {
            "subject": "Help",
            "description": "Please call me",
            "customer_email": "not-an-email",
        },
    )
    assert result["created"] is False
    assert store.query("tickets", "ticket") == []


def test_unknown_tool_returns_an_error_payload():
    tools, _store = _registry()
    result = tools.execute("delete_order", {})
    assert result["ok"] is False
