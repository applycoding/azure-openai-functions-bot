"""Sample orders shipped with the demo store."""

from __future__ import annotations

from supportbot.storage import TableStore

ORDERS_TABLE = "orders"
TICKETS_TABLE = "tickets"
MESSAGES_TABLE = "messages"

SAMPLE_ORDERS: tuple[dict[str, object], ...] = (
    {
        "PartitionKey": "order",
        "RowKey": "ORD-1001",
        "order_id": "ORD-1001",
        "status": "shipped",
        "item": "Wireless headphones",
        "customer_email": "ada@example.com",
        "total_cents": 7999,
        "carrier": "Contoso Freight",
        "tracking_number": "CF1001001",
    },
    {
        "PartitionKey": "order",
        "RowKey": "ORD-1002",
        "order_id": "ORD-1002",
        "status": "processing",
        "item": "Mechanical keyboard",
        "customer_email": "lin@example.com",
        "total_cents": 12900,
        "carrier": "",
        "tracking_number": "",
    },
    {
        "PartitionKey": "order",
        "RowKey": "ORD-1003",
        "order_id": "ORD-1003",
        "status": "delivered",
        "item": "USB-C dock",
        "customer_email": "sam@example.com",
        "total_cents": 8900,
        "carrier": "Contoso Freight",
        "tracking_number": "CF1003003",
    },
)


def seed_orders(store: TableStore) -> None:
    """Insert sample orders that are not already present."""
    for order in SAMPLE_ORDERS:
        row_key = str(order["RowKey"])
        if store.get(ORDERS_TABLE, "order", row_key) is None:
            store.upsert(ORDERS_TABLE, dict(order))
