import pytest

from supportbot.azure_tables import AzureTableStore
from supportbot.seed import seed_orders
from supportbot.storage import InMemoryTableStore
from tests.fakes import FakeTableService


def test_memory_store_isolates_callers_and_partitions():
    store = InMemoryTableStore()
    entity = {"PartitionKey": "c", "RowKey": "000002", "role": "assistant"}
    store.upsert("messages", entity)
    entity["role"] = "changed"
    store.upsert("messages", {"PartitionKey": "c", "RowKey": "000001", "role": "user"})
    store.upsert("messages", {"PartitionKey": "other", "RowKey": "000000", "role": "user"})

    rows = store.query("messages", "c")
    assert [row["RowKey"] for row in rows] == ["000001", "000002"]
    assert store.get("messages", "c", "000002")["role"] == "assistant"
    assert store.get("messages", "c", "missing") is None


def test_seed_orders_are_idempotent():
    store = InMemoryTableStore()
    seed_orders(store)
    seed_orders(store)
    orders = store.query("orders", "order")
    assert [order["RowKey"] for order in orders] == ["ORD-1001", "ORD-1002", "ORD-1003"]


def test_azure_table_adapter_uses_the_injected_client():
    service = FakeTableService()
    store = AzureTableStore(service)
    store.upsert("orders", {"PartitionKey": "order", "RowKey": "ORD-1001", "status": "shipped"})
    assert store.get("orders", "order", "ORD-1001")["status"] == "shipped"
    assert store.get("orders", "order", "ORD-9999") is None
    assert [row["RowKey"] for row in store.query("orders", "order")] == ["ORD-1001"]
    assert service.created == ["orders"]


def test_azure_table_adapter_rejects_unsafe_partition_keys():
    store = AzureTableStore(FakeTableService())
    with pytest.raises(ValueError):
        store.query("orders", "order' or true")
