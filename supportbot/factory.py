"""Wire settings, secrets, storage, and the chat service.

Azure SDK clients are constructed here. Tests pass fakes into the builders and
do not contact Key Vault, Azure OpenAI, or Table Storage.
"""

from __future__ import annotations

from typing import Any

from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.keyvault.secrets import SecretClient as AzureSecretClient
from openai import AzureOpenAI

from supportbot.azure_tables import AzureTableStore
from supportbot.chat import ChatService
from supportbot.config import ConfigError, Settings, load_settings
from supportbot.llm import AzureOpenAIChatClient, ChatClient, OfflineToolRouter
from supportbot.memory import ConversationMemory
from supportbot.safety import ContentSafetyGuard
from supportbot.secrets import EnvSecretResolver, KeyVaultSecretResolver, SecretClient, SecretResolver
from supportbot.seed import seed_orders
from supportbot.storage import InMemoryTableStore, TableStore
from supportbot.tools import ToolRegistry

_TOKEN_SCOPE = "https://cognitiveservices.azure.com/.default"


def build_chat_service() -> ChatService:
    settings = load_settings()
    secrets = build_secret_resolver(settings)
    store = build_store(settings, secrets)
    return ChatService(
        llm=build_llm(settings, secrets),
        memory=ConversationMemory(store),
        tools=ToolRegistry(store),
        safety=ContentSafetyGuard(),
    )


def build_secret_resolver(settings: Settings, client: SecretClient | None = None) -> SecretResolver:
    if settings.key_vault_url:
        resolved = client
        if resolved is None:
            credential = _credential()
            resolved = AzureSecretClient(vault_url=settings.key_vault_url, credential=credential)
        return KeyVaultSecretResolver(resolved)
    return EnvSecretResolver()


def build_llm(
    settings: Settings,
    secrets: SecretResolver,
    azure_client: Any | None = None,
) -> ChatClient:
    if settings.llm_backend == "offline":
        return OfflineToolRouter()
    if settings.llm_backend == "azure":
        return build_azure_llm(settings, secrets, azure_client)
    raise ConfigError(f"Unsupported LLM_BACKEND: {settings.llm_backend}.")


def build_azure_llm(
    settings: Settings,
    secrets: SecretResolver,
    azure_client: Any | None = None,
) -> AzureOpenAIChatClient:
    if not settings.azure_openai_endpoint:
        raise ConfigError("AZURE_OPENAI_ENDPOINT is required when LLM_BACKEND=azure.")
    client = azure_client if azure_client is not None else _create_azure_openai(settings, secrets)
    return AzureOpenAIChatClient(client, settings.azure_openai_deployment)


def build_store(
    settings: Settings,
    secrets: SecretResolver,
    table_service: Any | None = None,
) -> TableStore:
    if settings.storage_backend == "memory":
        store: TableStore = InMemoryTableStore()
    elif settings.storage_backend == "table":
        service = table_service if table_service is not None else _create_table_service(settings, secrets)
        store = AzureTableStore(service)
    else:
        raise ConfigError(f"Unsupported STORAGE_BACKEND: {settings.storage_backend}.")
    if settings.seed_sample_data:
        seed_orders(store)
    return store


def _create_azure_openai(settings: Settings, secrets: SecretResolver) -> AzureOpenAI:
    endpoint = settings.azure_openai_endpoint
    if endpoint is None:
        raise ConfigError("AZURE_OPENAI_ENDPOINT is required when LLM_BACKEND=azure.")
    if settings.use_managed_identity:
        token_provider = get_bearer_token_provider(_credential(), _TOKEN_SCOPE)
        return AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=settings.azure_openai_api_version,
        )
    api_key = secrets.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        raise ConfigError("AZURE_OPENAI_API_KEY is required when USE_MANAGED_IDENTITY=false.")
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=settings.azure_openai_api_version,
    )


def _create_table_service(settings: Settings, secrets: SecretResolver) -> TableServiceClient:
    if settings.use_managed_identity and settings.storage_account_url:
        return TableServiceClient(endpoint=settings.storage_account_url, credential=_credential())
    connection = secrets.get("STORAGE_CONNECTION_STRING")
    if not connection:
        raise ConfigError(
            "STORAGE_ACCOUNT_URL with USE_MANAGED_IDENTITY, or STORAGE_CONNECTION_STRING, is required."
        )
    return TableServiceClient.from_connection_string(connection)


def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)
