"""Zero-dependency local HTTP server for the portfolio demo.

The Azure Functions host remains the deployment entry point. This server calls
the same handlers so the chat contract can be exercised without Core Tools,
Azurite, or cloud credentials. The default LLM backend is the offline router.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from supportbot.config import load_settings
from supportbot.factory import build_chat_service
from supportbot.httpapi import handle_chat, handle_health

logger = logging.getLogger(__name__)


class ChatHandler(BaseHTTPRequestHandler):
    service = None

    def do_GET(self) -> None:
        if _path(self.path) == "/api/health":
            status, payload = handle_health()
            self._send(status, payload)
            return
        self._send(404, {"error": "Not found."})

    def do_POST(self) -> None:
        if _path(self.path) != "/api/chat":
            self._send(404, {"error": "Not found."})
            return
        body = _read_json(self)
        status, payload = handle_chat(self.service, body)
        self._send(status, payload)

    def _send(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt: str, *args: object) -> None:
        logger.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings()
    ChatHandler.service = build_chat_service()
    server = ThreadingHTTPServer((settings.host, settings.port), ChatHandler)
    logger.info("Support assistant listening on http://%s:%s", settings.host, settings.port)
    logger.info("LLM backend: %s. Storage backend: %s.", settings.llm_backend, settings.storage_backend)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping")
        server.server_close()


def _path(raw: str) -> str:
    path = raw.split("?", 1)[0]
    if len(path) > 1 and path.endswith("/"):
        return path[:-1]
    return path


def _read_json(handler: BaseHTTPRequestHandler) -> object:
    length_raw = handler.headers.get("Content-Length", "0")
    try:
        length = int(length_raw)
    except ValueError:
        return None
    if length < 0:
        return None
    raw = handler.rfile.read(length) if length else b""
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
