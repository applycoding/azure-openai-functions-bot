import pytest

from supportbot.config import ConfigError, load_settings
from supportbot.factory import build_llm, build_secret_resolver, build_store
from supportbot.llm import AzureOpenAIChatClient, OfflineToolRouter
from supportbot.secrets import EnvSecretResolver, KeyVaultSecretResolver
from tests.fakes import FakeSecretClient, FakeTableService


def test_defaults_are_offline_and_in_memory():
    settings = load_settings({})
    assert settings.llm_backend == "offline"
    assert settings.storage_backend == "memory"
    assert settings.use_managed_identity is False
    assert settings.seed_sample_data is True
    assert settings.key_vault_url is None
    assert settings.port == 8741


def test_table_backend_does_not_seed_unless_asked():
    settings = load_settings({"STORAGE_BACKEND": "table"})
    assert settings.seed_sample_data is False


def test_invalid_backend_and_boolean_and_port():
    with pytest.raises(ConfigError):
        load_settings({"LLM_BACKEND": "local-gpu"})
    with pytest.raises(ConfigError):
        load_settings({"USE_MANAGED_IDENTITY": "maybe"})
    with pytest.raises(ConfigError):
        load_settings({"PORT": "zero"})


def test_env_resolver_ignores_blank_values():
    resolver = EnvSecretResolver({"AZURE_OPENAI_API_KEY": "  ", "STORAGE_CONNECTION_STRING": "UseDevelopment=no"})
    assert resolver.get("AZURE_OPENAI_API_KEY") is None
    assert resolver.get("STORAGE_CONNECTION_STRING") == "UseDevelopment=no"


def test_key_vault_resolver_uses_hyphenated_secret_names():
    client = FakeSecretClient({"azure-openai-api-key": "from-vault", "storage-connection-string": "   "})
    resolver = KeyVaultSecretResolver(client)
    assert resolver.get("AZURE_OPENAI_API_KEY") == "from-vault"
    assert resolver.get("STORAGE_CONNECTION_STRING") is None
    assert resolver.get("UNMAPPED") is None
    missing = KeyVaultSecretResolver(FakeSecretClient({}))
    assert missing.get("AZURE_OPENAI_API_KEY") is None
    assert client.calls == ["azure-openai-api-key", "storage-connection-string"]


def test_factory_selects_key_vault_when_a_client_is_injected():
    settings = load_settings({"KEY_VAULT_URL": "https://example.vault.azure.net/"})
    resolver = build_secret_resolver(settings, client=FakeSecretClient({"azure-openai-api-key": "k"}))
    assert isinstance(resolver, KeyVaultSecretResolver)
    assert resolver.get("AZURE_OPENAI_API_KEY") == "k"


def test_factory_offline_and_azure_branches():
    offline = build_llm(load_settings({"LLM_BACKEND": "offline"}), EnvSecretResolver({}))
    assert isinstance(offline, OfflineToolRouter)

    sentinel = object()
    azure = build_llm(
        load_settings(
            {
                "LLM_BACKEND": "azure",
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4o-mini",
            }
        ),
        EnvSecretResolver({}),
        azure_client=sentinel,
    )
    assert isinstance(azure, AzureOpenAIChatClient)
    assert azure.client is sentinel


def test_azure_builder_requires_endpoint_and_key_without_calling_azure():
    with pytest.raises(ConfigError, match="AZURE_OPENAI_ENDPOINT"):
        build_llm(load_settings({"LLM_BACKEND": "azure"}), EnvSecretResolver({}))
    with pytest.raises(ConfigError, match="AZURE_OPENAI_API_KEY"):
        build_llm(
            load_settings(
                {
                    "LLM_BACKEND": "azure",
                    "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
                    "USE_MANAGED_IDENTITY": "false",
                }
            ),
            EnvSecretResolver({}),
        )


def test_table_store_can_be_injected_and_seeded():
    service = FakeTableService()
    settings = load_settings({"STORAGE_BACKEND": "table", "SEED_SAMPLE_DATA": "true"})
    store = build_store(settings, EnvSecretResolver({}), table_service=service)
    assert store.get("orders", "order", "ORD-1003")["status"] == "delivered"
    assert "orders" in service.created


def test_table_store_requires_a_connection_when_identity_is_off():
    settings = load_settings({"STORAGE_BACKEND": "table", "USE_MANAGED_IDENTITY": "false"})
    with pytest.raises(ConfigError, match="STORAGE_CONNECTION_STRING"):
        build_store(settings, EnvSecretResolver({}))
