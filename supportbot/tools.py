"""Order lookup and support-ticket tools."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from supportbot.seed import ORDERS_TABLE, TICKETS_TABLE
from supportbot.storage import TableStore

ORDER_ID = re.compile(r"ORD-\d{4}")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_ORDER_FIELDS = (
    "order_id",
    "status",
    "item",
    "customer_email",
    "total_cents",
    "carrier",
    "tracking_number",
)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up one Contoso Shop order by its order id, such as ORD-1001.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Order id, for example ORD-1001.",
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": (
                "Open a support ticket when the customer wants a person to follow up, "
                "or reports a refund, damage, or missing item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Short ticket subject."},
                    "description": {
                        "type": "string",
                        "description": "What the customer needs help with.",
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "Email address for the follow-up.",
                    },
                    "order_id": {
                        "type": "string",
                        "description": "Related order id, if the customer gave one.",
                    },
                },
                "required": ["subject", "description", "customer_email"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolRegistry:
    def __init__(self, store: TableStore) -> None:
        self._store = store

    def definitions(self) -> list[dict[str, Any]]:
        return TOOL_DEFINITIONS

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "lookup_order":
            return self.lookup_order(arguments)
        if name == "create_ticket":
            return self.create_ticket(arguments)
        return {"ok": False, "message": f"Unknown tool: {name}"}

    def lookup_order(self, arguments: dict[str, Any]) -> dict[str, Any]:
        order_id = str(arguments.get("order_id", "")).strip().upper()
        if not ORDER_ID.fullmatch(order_id):
            return {"found": False, "message": "order_id must look like ORD-1001."}
        entity = self._store.get(ORDERS_TABLE, "order", order_id)
        if entity is None:
            return {
                "found": False,
                "order_id": order_id,
                "message": f"No order {order_id} was found.",
            }
        return {"found": True, "order": {field: entity.get(field, "") for field in _ORDER_FIELDS}}

    def create_ticket(self, arguments: dict[str, Any]) -> dict[str, Any]:
        subject = str(arguments.get("subject", "")).strip()
        description = str(arguments.get("description", "")).strip()
        email = str(arguments.get("customer_email", "")).strip()
        order_id = str(arguments.get("order_id", "")).strip().upper()
        if not subject or not description:
            return {"created": False, "message": "subject and description are required."}
        if len(subject) > 120 or len(description) > 2000:
            return {"created": False, "message": "subject or description is too long."}
        if not EMAIL.fullmatch(email):
            return {"created": False, "message": "A valid customer_email is required to open a ticket."}
        if order_id and not ORDER_ID.fullmatch(order_id):
            return {"created": False, "message": "order_id must look like ORD-1001."}
        ticket_id = f"TCK-{uuid4().hex[:8].upper()}"
        created_at = datetime.now(timezone.utc).isoformat()
        entity = {
            "PartitionKey": "ticket",
            "RowKey": ticket_id,
            "ticket_id": ticket_id,
            "subject": subject,
            "description": description,
            "customer_email": email,
            "order_id": order_id,
            "status": "open",
            "created_at": created_at,
        }
        self._store.upsert(TICKETS_TABLE, entity)
        return {
            "created": True,
            "ticket": {
                "ticket_id": ticket_id,
                "subject": subject,
                "description": description,
                "customer_email": email,
                "order_id": order_id,
                "status": "open",
                "created_at": created_at,
            },
        }
