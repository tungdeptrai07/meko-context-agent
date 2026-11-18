"""Unit and integration tests for MekoMemoir Shared Context & Token Efficiency Engine."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.meko_engine import MekoCloudClient, SharedContextEngine
from backend.server import create_server


class _FakeMekoCloudHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/health":
            payload = {"data": {"data_database": "ok", "database": "ok", "status": "ok"}}
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_response(404)
        self.end_headers()


class TestMekoContextEngine(unittest.TestCase):
    """Tests Meko health check, shared memory ingestion, promotion, and token savings."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.mock_meko = HTTPServer(("127.0.0.1", 0), _FakeMekoCloudHandler)
        m_port = cls.mock_meko.server_address[1]
        threading.Thread(target=cls.mock_meko.serve_forever, daemon=True).start()

        client = MekoCloudClient(rest_base=f"http://127.0.0.1:{m_port}")
        cls.engine = SharedContextEngine(client=client)
        cls.srv = create_server(port=0, engine=cls.engine)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.mock_meko.shutdown()
        cls.mock_meko.server_close()
        cls.srv.shutdown()
        cls.srv.server_close()

    def test_health_and_token_efficiency_search(self) -> None:
        self.assertTrue(self.engine.cloud_health["reachable"])
        res = self.engine.retrieve_context_and_measure(
            consumer_agent="CoderAgent",
            query="Why did Meko endpoints return 403 without User-Agent and Bearer header?",
            top_k=2,
        )
        self.assertGreater(res.savings_pct, 60.0)
        self.assertGreater(res.tokens_saved, 0)
        self.assertTrue(any("User-Agent" in ch["content"] for ch in res.matched_chunks))

    def test_ingest_and_self_learning_promotion(self) -> None:
        mem = self.engine.ingest_memory(
            author_agent="FraudAgent",
            kind="memory",
            title="Velocity Anomaly Rule",
            content="Flag wallets executing more than 12 micro-transfers across new contracts within 60 seconds.",
        )
        self.assertFalse(mem.promoted)
        promoted = self.engine.promote_memory(mem.memory_id)
        self.assertTrue(promoted.promoted)
        self.assertGreater(promoted.utility_score, 0.80)

    def test_http_api_end_to_end(self) -> None:
        s_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/search",
            data=json.dumps({"consumerAgent": "PlannerAgent", "query": "YugabyteDB composite primary key", "topK": 2}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(s_req, timeout=5) as r1:
            d1 = json.loads(r1.read().decode("utf-8"))
        self.assertGreater(d1["result"]["savings_pct"], 50.0)
        self.assertGreaterEqual(d1["state"]["metrics"]["queriesExecuted"], 1)


if __name__ == "__main__":
    unittest.main()
