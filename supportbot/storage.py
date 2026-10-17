"""Table storage port and an in-memory implementation.

Tests and the default local process use the in-memory store. No Azurite
emulator is required. The Azure Tables adapter lives in azure_tables.py.
"""

from __future__ import annotations

from typing import Any, Protocol


class TableStore(Protocol):
    def get(self, table: str, partition_key: str, row_key: str) -> dict[str, Any] | None:
        """Return one entity, or None when it is missing."""

    def upsert(self, table: str, entity: dict[str, Any]) -> None:
        """Insert or replace an entity that includes PartitionKey and RowKey."""

    def query(self, table: str, partition_key: str) -> list[dict[str, Any]]:
        """Return entities in one partition, ordered by row key."""


class InMemoryTableStore:
    def __init__(self) -> None:
        self._tables: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}

    def get(self, table: str, partition_key: str, row_key: str) -> dict[str, Any] | None:
        entity = self._tables.get(table, {}).get((partition_key, row_key))
        if entity is None:
            return None
        return dict(entity)

    def upsert(self, table: str, entity: dict[str, Any]) -> None:
        partition_key = str(entity["PartitionKey"])
        row_key = str(entity["RowKey"])
        self._tables.setdefault(table, {})[(partition_key, row_key)] = dict(entity)

    def query(self, table: str, partition_key: str) -> list[dict[str, Any]]:
        rows = [
            dict(entity)
            for (row_partition, _), entity in self._tables.get(table, {}).items()
            if row_partition == partition_key
        ]
        rows.sort(key=lambda entity: str(entity["RowKey"]))
        return rows
