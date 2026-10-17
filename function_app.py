"""Azure Functions (Python v2) entry points for the support assistant."""

from __future__ import annotations

import json
import logging

import azure.functions as func

from supportbot.chat import ChatService
from supportbot.factory import build_chat_service
from supportbot.httpapi import handle_chat, handle_health

logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
_service: ChatService | None = None


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = build_chat_service()
    return _service


@app.route(route="chat", methods=["POST"])
def chat(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("chat request")
    try:
        body = req.get_json()
    except ValueError:
        body = None
    status, payload = handle_chat(get_chat_service(), body)
    return func.HttpResponse(json.dumps(payload), status_code=status, mimetype="application/json")


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("health %s", req.method)
    status, payload = handle_health()
    return func.HttpResponse(json.dumps(payload), status_code=status, mimetype="application/json")
