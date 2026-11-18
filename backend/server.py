"""HTTP server for MekoMemoir Shared Context & Token Efficiency Copilot (port 8095)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.meko_engine import SharedContextEngine


class MekoHTTPHandler(SimpleHTTPRequestHandler):
    """Serves MekoMemoir Web UI and REST endpoints."""

    engine = SharedContextEngine()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "MekoMemoir Shared Context & Token Efficiency Copilot",
                    "mekoCloud": self.engine.cloud_health,
                }
            )
            return

        if self.path == "/api/state":
            self._send_json(self.engine.get_dashboard_state())
            return

        if self.path in {"", "/"}:
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 128_000))
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            self._send_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            if self.path == "/api/search":
                res = self.engine.retrieve_context_and_measure(
                    consumer_agent=str(data.get("consumerAgent", "CoderAgent")),
                    query=str(data.get("query", "")),
                    top_k=int(data.get("topK", 2)),
                )
                self._send_json({"result": asdict(res), "state": self.engine.get_dashboard_state()})
                return

            if self.path == "/api/ingest":
                mem = self.engine.ingest_memory(
                    author_agent=str(data.get("authorAgent", "PlannerAgent")),
                    kind=str(data.get("kind", "memory")),
                    title=str(data.get("title", "")),
                    content=str(data.get("content", "")),
                )
                self._send_json({"memory": asdict(mem), "state": self.engine.get_dashboard_state()})
                return

            if self.path == "/api/promote":
                mem = self.engine.promote_memory(str(data.get("memoryId", "")))
                self._send_json({"memory": asdict(mem), "state": self.engine.get_dashboard_state()})
                return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8095,
    engine: SharedContextEngine | None = None,
) -> ThreadingHTTPServer:
    """Create the MekoMemoir HTTP server."""

    class BoundHandler(MekoHTTPHandler):
        pass

    BoundHandler.engine = engine or SharedContextEngine()
    return ThreadingHTTPServer((host, port), BoundHandler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8095"))
    srv = create_server(port=port)
    print(f"MekoMemoir running on http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()
