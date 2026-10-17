"""Azure Table Storage adapter.

The Functions app uses this when STORAGE_BACKEND=table. Authentication is a
managed-identity credential against STORAGE_ACCOUNT_URL, or a connection
string read from Key Vault / the environment. Unit tests inject a fake
service client and do not start Azurite.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Protocol

from azure.core.exceptions import ResourceNotFoundError

_KEY = re.compile(r"[A-Za-z0-9-]{1,64}")


class TableClient(Protocol):
    def get_entity(self, partition_key: str, row_key: str) -> dict[str, Any]:
        """Return one entity or raise if it is missing."""

    def upsert_entity(self, entity: dict[str, Any]) -> None:
        """Insert or replace an entity."""

    def query_entities(self, query_filter: str) -> Iterable[dict[str, Any]]:
        """Return entities matching an OData filter."""


class TableService(Protocol):
    def create_table_if_not_exists(self, table_name: str) -> object:
        """Create the table when it is missing."""

    def get_table_client(self, table_name: str) -> TableClient:
        """Return a client for one table."""


def partition_filter(partition_key: str) -> str:
    if not _KEY.fullmatch(partition_key):
        raise ValueError("Unsupported partition key")
    return f"PartitionKey eq '{partition_key}'"


class AzureTableStore:
    def __init__(self, service: TableService) -> None:
        self._service = service
        self._ready: set[str] = set()

    def _client(self, table: str):
        if table not in self._ready:
            self._service.create_table_if_not_exists(table)
            self._ready.add(table)
        return self._service.get_table_client(table)

    def get(self, table: str, partition_key: str, row_key: str) -> dict[str, Any] | None:
        try:
            entity = self._client(table).get_entity(partition_key, row_key)
        except ResourceNotFoundError:
            return None
        return dict(entity)

    def upsert(self, table: str, entity: dict[str, Any]) -> None:
        self._client(table).upsert_entity(entity)

    def query(self, table: str, partition_key: str) -> list[dict[str, Any]]:
        rows = [
            dict(entity)
            for entity in self._client(table).query_entities(query_filter=partition_filter(partition_key))
        ]
        rows.sort(key=lambda entity: str(entity["RowKey"]))
        return rows
