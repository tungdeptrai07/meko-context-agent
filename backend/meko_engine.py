"""MekoMemoir — Multi-Agent Shared Context, Self-Learning & Token Efficiency Engine.

Built for ContextCon: Remember Everything (HackerEarth / YugabyteDB Meko Context Engine).
Integrates:
- Meko Cloud Datapack REST API (`https://api.mekodata.ai/api/v1`)
- Meko Cloud MCP Server JSON-RPC (`https://mcp.mekodata.ai/mcp`)
- Real-time Token Efficiency telemetry (`track_token_usage` comparison: Full History vs. Meko Context Slices)
- Self-Learning Memory Promotion (`POST /promote-memories`) and Decision Audit Trace.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

MEKO_REST_BASE = "https://api.mekodata.ai/api/v1"
MEKO_MCP_ENDPOINT = "https://mcp.mekodata.ai/mcp"
USER_AGENT = "MekoMemoir/1.0 (ContextCon-Hackathon)"


def estimate_tokens(text: str) -> int:
    """Deterministic subword-aware token count estimator (~3.7 chars/token)."""
    cleaned = (text or "").strip()
    if not cleaned:
        return 0
    words = len(cleaned.split())
    char_est = math.ceil(len(cleaned) / 3.7)
    return max(words, char_est)


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(t) >= 2]


@dataclass
class MemoryChunk:
    """A structured memory / conversation / artifact entry inside a Meko Datapack."""

    memory_id: str
    datapack_id: str
    author_agent: str
    kind: str  # "conversation", "memory", "artifact", "self_learning"
    title: str
    content: str
    tokens: int
    promoted: bool
    utility_score: float
    content_hash: str
    created_at: float


@dataclass
class ContextRetrievalResult:
    """Measures token efficiency & provenance of a Meko `context_search` query."""

    query_id: str
    consumer_agent: str
    query: str
    baseline_full_history_tokens: int
    retrieved_context_tokens: int
    tokens_saved: int
    savings_pct: float
    matched_chunks: list[dict[str, Any]]
    audit_note: str
    timestamp: float


class MekoCloudClient:
    """HTTP/MCP adapter for Meko Cloud (`Authorization: Bearer mko_tkn_...`, `User-Agent`)."""

    def __init__(
        self,
        api_key: str | None = None,
        rest_base: str = MEKO_REST_BASE,
        mcp_url: str = MEKO_MCP_ENDPOINT,
        timeout_s: float = 6.0,
    ) -> None:
        self.api_key = (api_key or os.environ.get("MEKO_API_KEY", "")).strip()
        self.rest_base = rest_base.rstrip("/")
        self.mcp_url = mcp_url
        self.timeout_s = timeout_s
        self._rpc_id = 0

    def _headers(self, include_auth: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if include_auth and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def check_health(self) -> dict[str, Any]:
        """Call public `GET /api/v1/health` (no API key required)."""
        try:
            req = urllib.request.Request(
                f"{self.rest_base}/health",
                headers=self._headers(include_auth=False),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return {"reachable": True, "httpStatus": resp.status, "payload": body.get("data", body)}
        except Exception as exc:
            return {"reachable": False, "error": str(exc)}

    def create_datapack(self, name: str, description: str) -> dict[str, Any]:
        """Call `POST /api/v1/datapacks` when an API key is configured."""
        if not self.api_key:
            return {"mode": "local_mirror", "status": "no_api_key"}
        req = urllib.request.Request(
            f"{self.rest_base}/datapacks",
            data=json.dumps({"name": name, "description": description}).encode("utf-8"),
            headers=self._headers(include_auth=True),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return {"mode": "meko_cloud", "data": json.loads(resp.read().decode("utf-8"))}

    def call_mcp_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a remote Meko MCP tool via JSON-RPC 2.0 (`tools/call`)."""
        if not self.api_key:
            return {"mode": "local_mirror", "tool": tool_name}
        self._rpc_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._rpc_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        req = urllib.request.Request(
            self.mcp_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(include_auth=True),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return {"mode": "meko_cloud", "data": json.loads(resp.read().decode("utf-8"))}


SEED_MEMORIES = [
    (
        "PlannerAgent",
        "artifact",
        "YugabyteDB Postgres Schema & Indexing Policy",
        "All financial ledger tables must use composite primary keys (tenant_id, account_id, created_at) with hash sharding on tenant_id and strict serializable isolation for balance updates.",
        True,
        0.95,
    ),
    (
        "SecurityAgent",
        "self_learning",
        "Meko Authentication & Mandatory User-Agent Lesson",
        "Lesson learned from API 403 failures: Meko Cloud REST and MCP endpoints reject requests lacking a User-Agent header and ignore X-Api-Key; always pass Authorization: Bearer mko_tkn_... and User-Agent.",
        True,
        0.98,
    ),
    (
        "CoderAgent",
        "conversation",
        "Payment Retry Idempotency Pattern",
        "When dispatching webhook retries or idempotent settlement transactions, derive an idempotency key from SHA-256(tenant_id + invoice_id + epoch_window) stored with unique constraint.",
        False,
        0.82,
    ),
    (
        "ComplianceAgent",
        "memory",
        "PII Redaction Rule for Conversation Capture",
        "Before calling conversation_add_message or storing shared memory datapacks, mask government IDs, email locals, and raw bearer tokens so downstream agents never ingest unmasked credentials.",
        True,
        0.91,
    ),
    (
        "ReviewerAgent",
        "conversation",
        "CI Benchmark: Token Usage & Latency Baseline",
        "Naive full-history prompt replay averaged 6,420 tokens across 14 multi-agent turns; switching to Meko context_search with top-2 promoted slices reduced prompt size below 650 tokens.",
        False,
        0.86,
    ),
    (
        "CoderAgent",
        "memory",
        "Datapack Slot Conservation Guideline",
        "Meko Cloud free tier caps Datapacks at 10 creations total (deleting a datapack does not restore a creation slot), so consolidate project domains inside a single shared datapack namespace.",
        True,
        0.89,
    ),
]


class SharedContextEngine:
    """Manages shared multi-agent memories, promotion loops, and token telemetry."""

    def __init__(self, client: MekoCloudClient | None = None) -> None:
        self.client = client or MekoCloudClient()
        self.datapack_id = "dp_adlc_shared_core"
        self.memories: dict[str, MemoryChunk] = {}
        self.retrievals: list[ContextRetrievalResult] = []
        self.audit_trail: list[dict[str, Any]] = []
        self.cloud_health: dict[str, Any] = self.client.check_health()

        for agent, kind, title, content, promoted, score in SEED_MEMORIES:
            self.ingest_memory(
                author_agent=agent,
                kind=kind,
                title=title,
                content=content,
                promoted=promoted,
                utility_score=score,
            )

    def _log_audit(self, event: str, actor: str, detail: str) -> None:
        self.audit_trail.append(
            {
                "seq": len(self.audit_trail) + 1,
                "event": event,
                "actor": actor,
                "detail": detail,
                "timestamp": round(time.time(), 3),
            }
        )

    def ingest_memory(
        self,
        author_agent: str,
        kind: str,
        title: str,
        content: str,
        promoted: bool = False,
        utility_score: float = 0.80,
    ) -> MemoryChunk:
        """Store a new conversation/memory/artifact/self-learning unit in the shared datapack."""
        clean_title = (title or "").strip()
        clean_content = (content or "").strip()
        if not clean_title or not clean_content:
            raise ValueError("Both 'title' and 'content' are required.")

        c_hash = "sha256:" + hashlib.sha256(f"{clean_title}:{clean_content}".encode("utf-8")).hexdigest()[:16]
        mem_id = f"mem_{len(self.memories) + 1:03d}"
        tokens = estimate_tokens(f"{clean_title}. {clean_content}")

        chunk = MemoryChunk(
            memory_id=mem_id,
            datapack_id=self.datapack_id,
            author_agent=author_agent.strip() or "Agent",
            kind=kind.strip() or "memory",
            title=clean_title,
            content=clean_content,
            tokens=tokens,
            promoted=promoted,
            utility_score=round(float(utility_score), 2),
            content_hash=c_hash,
            created_at=round(time.time(), 3),
        )
        self.memories[mem_id] = chunk
        self._log_audit(
            "MEMORY_INGESTED",
            chunk.author_agent,
            f"Stored {chunk.kind} '{chunk.title}' ({chunk.tokens} tokens, {chunk.content_hash}).",
        )
        return chunk

    def promote_memory(self, memory_id: str) -> MemoryChunk:
        """Self-learning loop: promote a validated memory (`POST /promote-memories`)."""
        if memory_id not in self.memories:
            raise ValueError(f"Unknown memory_id: {memory_id}")
        chunk = self.memories[memory_id]
        chunk.promoted = True
        chunk.utility_score = min(1.0, round(chunk.utility_score + 0.08, 2))
        self._log_audit(
            "MEMORY_PROMOTED",
            "SelfLearningEvaluator",
            f"Promoted {memory_id} ('{chunk.title}') to durable Knowledge Base (utility={chunk.utility_score}).",
        )
        return chunk

    def retrieve_context_and_measure(
        self,
        consumer_agent: str,
        query: str,
        top_k: int = 2,
    ) -> ContextRetrievalResult:
        """Simulate Meko `context_search` + `track_token_usage` savings measurement."""
        clean_q = (query or "").strip()
        if not clean_q:
            raise ValueError("Query cannot be empty.")

        q_tokens = _tokenize(clean_q)
        if not q_tokens:
            raise ValueError("Query must contain searchable keywords.")

        raw_total = sum(m.tokens + 180 for m in self.memories.values())
        baseline_tokens = max(raw_total, 420)

        scored: list[tuple[float, MemoryChunk, list[str]]] = []
        for chunk in self.memories.values():
            doc_text = f"{chunk.title} {chunk.content} {chunk.kind}".lower()
            doc_toks = set(_tokenize(doc_text))
            hits = [qt for qt in set(q_tokens) if qt in doc_toks or qt in doc_text]
            if not hits:
                continue
            relevance = (len(hits) / len(set(q_tokens))) * 2.0
            promo_bonus = 0.45 if chunk.promoted else 0.0
            score = round(relevance + chunk.utility_score * 0.5 + promo_bonus, 3)
            scored.append((score, chunk, sorted(hits)))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[: max(1, min(top_k, 5))]

        retrieved_tokens = sum(ch.tokens for _, ch, _ in selected) + 32
        tokens_saved = max(0, baseline_tokens - retrieved_tokens)
        savings_pct = round((tokens_saved / max(baseline_tokens, 1)) * 100.0, 2)

        matched_payload = [
            {
                "memory_id": ch.memory_id,
                "author_agent": ch.author_agent,
                "kind": ch.kind,
                "title": ch.title,
                "content": ch.content,
                "tokens": ch.tokens,
                "promoted": ch.promoted,
                "score": sc,
                "matched_terms": hits,
            }
            for sc, ch, hits in selected
        ]

        res = ContextRetrievalResult(
            query_id=f"qry_{len(self.retrievals) + 1:03d}",
            consumer_agent=consumer_agent.strip() or "CoderAgent",
            query=clean_q,
            baseline_full_history_tokens=baseline_tokens,
            retrieved_context_tokens=retrieved_tokens,
            tokens_saved=tokens_saved,
            savings_pct=savings_pct,
            matched_chunks=matched_payload,
            audit_note=(
                f"Retrieved {len(selected)}/{len(self.memories)} chunks "
                f"({retrieved_tokens} vs {baseline_tokens} baseline tokens, saved {savings_pct}%)."
            ),
            timestamp=round(time.time(), 3),
        )
        self.retrievals.append(res)
        self._log_audit("CONTEXT_SEARCH_TRACKED", res.consumer_agent, res.audit_note)
        return res

    def get_dashboard_state(self) -> dict[str, Any]:
        """Return full shared context, token savings aggregates, and Meko Cloud health."""
        total_baseline = sum(r.baseline_full_history_tokens for r in self.retrievals)
        total_retrieved = sum(r.retrieved_context_tokens for r in self.retrievals)
        avg_savings = (
            round(((total_baseline - total_retrieved) / max(total_baseline, 1)) * 100.0, 2)
            if self.retrievals
            else 0.0
        )
        return {
            "datapackId": self.datapack_id,
            "mekoCloudHealth": self.cloud_health,
            "apiKeyConfigured": bool(self.client.api_key),
            "metrics": {
                "totalMemories": len(self.memories),
                "promotedMemories": sum(1 for m in self.memories.values() if m.promoted),
                "queriesExecuted": len(self.retrievals),
                "cumulativeTokensSaved": max(0, total_baseline - total_retrieved),
                "averageSavingsPct": avg_savings,
            },
            "memories": [asdict(m) for m in reversed(list(self.memories.values()))],
            "retrievals": [asdict(r) for r in reversed(self.retrievals[-10:])],
            "auditTrail": list(reversed(self.audit_trail[-15:])),
        }
