"""In-test stand-ins. No network, Azurite, or cloud credentials."""

from __future__ import annotations

from typing import Any

from azure.core.exceptions import ResourceNotFoundError

from supportbot.models import LLMResult, Message


class FakeChatClient:
    def __init__(self, results: list[LLMResult]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResult:
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self._results:
            raise AssertionError("FakeChatClient has no scripted results left")
        return self._results.pop(0)


class FakeSecret:
    def __init__(self, value: str | None) -> None:
        self.value = value


class FakeSecretClient:
    def __init__(self, secrets: dict[str, str | None]) -> None:
        self._secrets = secrets
        self.calls: list[str] = []

    def get_secret(self, name: str) -> FakeSecret:
        self.calls.append(name)
        if name not in self._secrets:
            raise ResourceNotFoundError(name)
        return FakeSecret(self._secrets[name])


class FakeTable:
    def __init__(self) -> None:
        self.entities: dict[tuple[str, str], dict[str, Any]] = {}

    def get_entity(self, partition_key: str, row_key: str) -> dict[str, Any]:
        key = (partition_key, row_key)
        if key not in self.entities:
            raise ResourceNotFoundError("missing")
        return dict(self.entities[key])

    def upsert_entity(self, entity: dict[str, Any]) -> None:
        self.entities[(str(entity["PartitionKey"]), str(entity["RowKey"]))] = dict(entity)

    def query_entities(self, query_filter: str) -> list[dict[str, Any]]:
        prefix = "PartitionKey eq '"
        if not query_filter.startswith(prefix) or not query_filter.endswith("'"):
            raise AssertionError(query_filter)
        partition = query_filter[len(prefix) : -1]
        return [dict(entity) for (row_partition, _), entity in self.entities.items() if row_partition == partition]


class FakeTableService:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}
        self.created: list[str] = []

    def create_table_if_not_exists(self, table_name: str) -> None:
        self.created.append(table_name)
        self.tables.setdefault(table_name, FakeTable())

    def get_table_client(self, table_name: str) -> FakeTable:
        return self.tables[table_name]
