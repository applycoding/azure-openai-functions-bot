"""Runtime settings.

Non-secret settings come from environment variables (Function App settings in
Azure). Secrets are resolved separately so Key Vault access stays in one place.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_LLM_BACKENDS = {"offline", "azure"}
_STORAGE_BACKENDS = {"memory", "table"}


class ConfigError(Exception):
    """The process configuration is incomplete or invalid."""


@dataclass(frozen=True)
class Settings:
    llm_backend: str
    storage_backend: str
    use_managed_identity: bool
    seed_sample_data: bool
    key_vault_url: str | None
    azure_openai_endpoint: str | None
    azure_openai_deployment: str
    azure_openai_api_version: str
    storage_account_url: str | None
    host: str
    port: int


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    llm_backend = _choice(env, "LLM_BACKEND", "offline", _LLM_BACKENDS)
    storage_backend = _choice(env, "STORAGE_BACKEND", "memory", _STORAGE_BACKENDS)
    return Settings(
        llm_backend=llm_backend,
        storage_backend=storage_backend,
        use_managed_identity=_flag(env, "USE_MANAGED_IDENTITY", False),
        seed_sample_data=_flag(env, "SEED_SAMPLE_DATA", storage_backend == "memory"),
        key_vault_url=_optional(env, "KEY_VAULT_URL"),
        azure_openai_endpoint=_optional(env, "AZURE_OPENAI_ENDPOINT"),
        azure_openai_deployment=_text(env, "AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
        azure_openai_api_version=_text(env, "AZURE_OPENAI_API_VERSION", "2024-10-21"),
        storage_account_url=_optional(env, "STORAGE_ACCOUNT_URL"),
        host=_text(env, "HOST", "0.0.0.0"),
        port=_port(env),
    )


def _choice(env: Mapping[str, str], name: str, default: str, allowed: set[str]) -> str:
    value = _text(env, name, default).lower()
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ConfigError(f"Unsupported {name}: {value}. Expected one of: {allowed_text}.")
    return value


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    value = str(raw).strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"Unsupported boolean for {name}: {raw}")


def _optional(env: Mapping[str, str], name: str) -> str | None:
    value = str(env.get(name, "")).strip()
    if not value:
        return None
    return value


def _text(env: Mapping[str, str], name: str, default: str) -> str:
    value = str(env.get(name, "")).strip()
    if not value:
        return default
    return value


def _port(env: Mapping[str, str]) -> int:
    raw = str(env.get("PORT", "")).strip()
    if not raw:
        return 8741
    try:
        port = int(raw)
    except ValueError as exc:
        raise ConfigError("PORT must be an integer.") from exc
    if port < 1 or port > 65535:
        raise ConfigError("PORT must be between 1 and 65535.")
    return port
