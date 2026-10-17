import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from supportbot.config import load_settings
from supportbot.factory import build_chat_service
from supportbot.httpapi import handle_chat, handle_health
from supportbot.llm import LLMError
from supportbot.local_server import ChatHandler
from supportbot.models import LLMResult
from tests.conftest import make_service
from tests.fakes import FakeChatClient


def test_health_reports_the_configured_backends():
    status, body = handle_health(load_settings({"LLM_BACKEND": "offline", "STORAGE_BACKEND": "memory"}))
    assert status == 200
    assert body["status"] == "ok"
    assert body["service"] == "support-assistant"
    assert body["llm_backend"] == "offline"
    assert body["storage_backend"] == "memory"


def test_chat_endpoint_validates_the_body_and_maps_model_errors():
    service, _store = make_service(FakeChatClient([LLMResult(content="Ready.", tool_calls=[])]))
    ok, payload = handle_chat(service, {"message": "Hello", "conversationId": "conv-http"})
    assert ok == 200
    assert payload["conversation_id"] == "conv-http"
    assert payload["reply"] == "Ready."

    missing, missing_body = handle_chat(service, {"message": "  "})
    assert missing == 400
    assert "message" in missing_body["error"]

    invalid, invalid_body = handle_chat(service, None)
    assert invalid == 400

    bad_id, bad_id_body = handle_chat(service, {"message": "Hi", "conversation_id": "has spaces"})
    assert bad_id == 400
    assert "conversation_id" in bad_id_body["error"]

    class Boom:
        def complete(self, messages, tools):
            raise LLMError("The language model request failed.")

    failed, failed_body = handle_chat(
        make_service(Boom())[0],
        {"message": "Hi"},
    )
    assert failed == 502
    assert failed_body["error"] == "The language model request failed."


def test_local_server_health_and_chat(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "offline")
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    monkeypatch.setenv("SEED_SAMPLE_DATA", "true")
    monkeypatch.delenv("KEY_VAULT_URL", raising=False)
    ChatHandler.service = build_chat_service()
    server = ThreadingHTTPServer(("127.0.0.1", 0), ChatHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        health = _read_json(f"http://127.0.0.1:{port}/api/health")
        assert health["status"] == "ok"

        payload = _read_json(
            urllib.request.Request(
                f"http://127.0.0.1:{port}/api/chat",
                data=json.dumps({"message": "Where is order ORD-1002?"}).encode(),
                headers={"Content-Type": "application/json"},
            )
        )
        assert payload["tool_calls"][0]["name"] == "lookup_order"
        assert "processing" in payload["reply"]

        bad = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/chat",
            data=b"not-json",
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(bad, timeout=2)
        assert caught.value.code == 400
    finally:
        server.shutdown()
        server.server_close()


def _read_json(request: urllib.request.Request | str) -> dict:
    last_error: Exception | None = None
    for _ in range(20):
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                body = json.loads(response.read().decode())
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            last_error = exc
            time.sleep(0.05)
            continue
        if not isinstance(body, dict):
            raise AssertionError("expected a JSON object")
        return body
    raise AssertionError(f"local server did not respond: {last_error}")
