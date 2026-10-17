from types import SimpleNamespace

import pytest

from supportbot.llm import AzureOpenAIChatClient, LLMError, parse_assistant_message, to_api_message
from supportbot.models import Message, ToolCall


class _Completions:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


class _FakeAzure:
    def __init__(self, completions: _Completions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def test_azure_client_parses_tool_calls_and_sends_messages():
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="lookup_order", arguments='{"order_id":"ORD-1001"}'),
    )
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call]))])
    completions = _Completions(response=response)
    client = AzureOpenAIChatClient(_FakeAzure(completions), "gpt-4o-mini")
    messages = [
        Message(role="system", content="Be brief."),
        Message(role="user", content="Where is ORD-1001?"),
    ]
    result = client.complete(messages, [{"type": "function", "function": {"name": "lookup_order"}}])

    assert result.tool_calls[0].name == "lookup_order"
    assert result.tool_calls[0].arguments == {"order_id": "ORD-1001"}
    assert completions.kwargs["model"] == "gpt-4o-mini"
    assert completions.kwargs["tool_choice"] == "auto"
    assert completions.kwargs["messages"][1]["content"] == "Where is ORD-1001?"


def test_azure_client_hides_provider_errors():
    completions = _Completions(error=RuntimeError("connection string leaked in the sdk error"))
    client = AzureOpenAIChatClient(_FakeAzure(completions), "gpt-4o-mini")
    with pytest.raises(LLMError) as caught:
        client.complete([Message(role="user", content="Hi")], [])
    assert str(caught.value) == "The language model request failed."
    assert "connection string" not in str(caught.value)


def test_invalid_tool_arguments_become_an_empty_object():
    message = SimpleNamespace(
        content="ok",
        tool_calls=[SimpleNamespace(id="1", function=SimpleNamespace(name="lookup_order", arguments="{"))],
    )
    parsed = parse_assistant_message(message)
    assert parsed.content == "ok"
    assert parsed.tool_calls[0].arguments == {}


def test_assistant_tool_call_message_uses_the_api_shape():
    payload = to_api_message(
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="call-9", name="lookup_order", arguments={"order_id": "ORD-1002"})],
        )
    )
    assert payload["tool_calls"][0]["type"] == "function"
    assert payload["tool_calls"][0]["function"]["arguments"] == '{"order_id": "ORD-1002"}'
    tool_payload = to_api_message(Message(role="tool", content="{}", tool_call_id="call-9", name="lookup_order"))
    assert tool_payload["role"] == "tool"
    assert tool_payload["tool_call_id"] == "call-9"
