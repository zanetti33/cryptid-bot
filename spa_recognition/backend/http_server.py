from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Tuple

from spa_recognition.backend.api import SpaRecognitionApi

_API = SpaRecognitionApi()


class _Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/setup", "/board-layout", "/map", "/structures", "/clues", "/recalculate"}:
            self._send_json({"error": f"Unknown path: {self.path}"}, HTTPStatus.NOT_FOUND)
            return

        body_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(body_length) if body_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON payload"}, HTTPStatus.BAD_REQUEST)
            return

        if not isinstance(payload, dict):
            self._send_json({"error": "Payload must be an object"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            result = _API.post(self.path, payload)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json(result.to_dict(), HTTPStatus.OK)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: dict, status: HTTPStatus) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def run(host: str = "127.0.0.1", port: int = 8000) -> Tuple[str, int]:
    server = ThreadingHTTPServer((host, port), _Handler)
    server.serve_forever()
    return host, port


if __name__ == "__main__":
    run()

