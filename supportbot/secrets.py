"""Secret lookup from the environment or from Key Vault."""

from __future__ import annotations

import os
from typing import Mapping, Protocol

from azure.core.exceptions import ResourceNotFoundError

# App setting name -> Key Vault secret name.
SECRET_NAMES = {
    "AZURE_OPENAI_API_KEY": "azure-openai-api-key",
    "STORAGE_CONNECTION_STRING": "storage-connection-string",
}


class SecretResolver(Protocol):
    def get(self, name: str) -> str | None:
        """Return a secret value, or None when it is unset."""


class SecretClient(Protocol):
    def get_secret(self, name: str) -> object:
        """Return an object with a value attribute."""


class EnvSecretResolver:
    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def get(self, name: str) -> str | None:
        value = str(self._environ.get(name, "")).strip()
        if not value:
            return None
        return value


class KeyVaultSecretResolver:
    def __init__(self, client: SecretClient, names: Mapping[str, str] | None = None) -> None:
        self._client = client
        self._names = dict(SECRET_NAMES if names is None else names)

    def get(self, name: str) -> str | None:
        vault_name = self._names.get(name)
        if vault_name is None:
            return None
        try:
            secret = self._client.get_secret(vault_name)
        except ResourceNotFoundError:
            return None
        value = getattr(secret, "value", None)
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text
