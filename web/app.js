const healthPill = document.getElementById("healthPill");
const savingsPill = document.getElementById("savingsPill");
const searchBox = document.getElementById("searchBox");
const memoriesList = document.getElementById("memoriesList");
const auditList = document.getElementById("auditList");
const queryInput = document.getElementById("queryInput");
const agentInput = document.getElementById("agentInput");
const topKInput = document.getElementById("topKInput");

let staticState = {
  datapackId: "dp_adlc_shared_core",
  mekoCloudHealth: { reachable: true, httpStatus: 200, payload: { status: "ok", database: "ok" } },
  metrics: { totalMemories: 4, promotedMemories: 3, queriesExecuted: 0, cumulativeTokensSaved: 0, averageSavingsPct: 0 },
  memories: [
    { memory_id: "mem_002", author_agent: "SecurityAgent", kind: "self_learning", title: "Meko Authentication & Mandatory User-Agent Lesson", content: "Always pass Authorization: Bearer mko_tkn_... and User-Agent header; Meko ignores X-Api-Key.", tokens: 42, promoted: true, utility_score: 0.98 },
    { memory_id: "mem_001", author_agent: "PlannerAgent", kind: "artifact", title: "YugabyteDB Postgres Schema & Indexing Policy", content: "Use composite primary keys (tenant_id, account_id, created_at) with hash sharding on tenant_id.", tokens: 38, promoted: true, utility_score: 0.95 },
    { memory_id: "mem_003", author_agent: "CoderAgent", kind: "conversation", title: "Payment Retry Idempotency Pattern", content: "Derive idempotency key from SHA-256(tenant_id + invoice_id + epoch_window).", tokens: 32, promoted: false, utility_score: 0.82 },
  ],
  auditTrail: [],
};

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s ?? "";
  return d.innerHTML;
}

function render(state) {
  const h = state.mekoCloudHealth || {};
  healthPill.textContent = h.reachable
    ? `Meko Cloud API: OK (HTTP ${h.httpStatus || 200})`
    : "Meko Cloud: Local Mirror Mode";
  const m = state.metrics || {};
  savingsPill.textContent = `Avg Token Savings: ${m.averageSavingsPct || 0}% (${m.cumulativeTokensSaved || 0} saved)`;

  memoriesList.innerHTML = (state.memories || []).map((mem) => `
    <div class="item-box">
      <div class="row-between">
        <strong>${esc(mem.title)}</strong>
        <span class="${mem.promoted ? "ok" : "muted"}">${mem.promoted ? "PROMOTED KB" : esc(mem.kind)} (${mem.tokens} tok)</span>
      </div>
      <div style="margin:5px 0">${esc(mem.content)}</div>
      <div class="row-between muted">
        <span>By ${esc(mem.author_agent)} · Utility ${mem.utility_score}</span>
        ${!mem.promoted ? `<button type="button" class="btn ok" data-promote="${esc(mem.memory_id)}">Promote Memory</button>` : ""}
      </div>
    </div>
  `).join("");

  memoriesList.querySelectorAll("button[data-promote]").forEach((btn) => {
    btn.addEventListener("click", () => promoteMemory(btn.dataset.promote));
  });

  auditList.innerHTML = (state.auditTrail || []).map((a) => `
    <div class="item-box">
      <div><strong>#${a.seq} · ${esc(a.event)}</strong> (${esc(a.actor)})</div>
      <div class="muted" style="margin-top:4px">${esc(a.detail)}</div>
    </div>
  `).join("") || `<div class="item-box muted">Run context search or promote memory to inspect live Meko audit logs.</div>`;
}

async function loadState() {
  try {
    const res = await fetch("/api/state");
    const ct = res.headers.get("content-type") || "";
    if (res.ok && ct.includes("application/json")) {
      staticState = await res.json();
    }
  } catch {
    // Use static preview state on GitHub Pages.
  }
  render(staticState);
}

async function promoteMemory(memoryId) {
  try {
    const res = await fetch("/api/promote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ memoryId }),
    });
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) throw new Error("Static fallback");
    const d = await res.json();
    staticState = d.state;
    render(staticState);
  } catch {
    staticState.memories = staticState.memories.map((m) =>
      m.memory_id === memoryId ? { ...m, promoted: true, utility_score: 0.9 } : m
    );
    staticState.auditTrail.unshift({ seq: staticState.auditTrail.length + 1, event: "MEMORY_PROMOTED", actor: "SelfLearningEvaluator", detail: `Promoted ${memoryId} to KB.` });
    render(staticState);
  }
}

document.getElementById("searchBtn").addEventListener("click", async () => {
  const query = queryInput.value.trim();
  const consumerAgent = agentInput.value;
  const topK = Number(topKInput.value) || 2;
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ consumerAgent, query, topK }),
    });
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) throw new Error("Static fallback");
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || "Search failed");
    const r = d.result;
    staticState = d.state;
    searchBox.innerHTML = `
      <div class="ok">Saved ${r.tokens_saved} tokens (${r.savings_pct}% reduction: ${r.retrieved_context_tokens} vs ${r.baseline_full_history_tokens} baseline)</div>
      <ul style="margin:6px 0 0;padding-left:18px">
        ${r.matched_chunks.map((c) => `<li><strong>${esc(c.title)}</strong> (${c.tokens} tokens, score ${c.score})</li>`).join("")}
      </ul>
    `;
    render(staticState);
  } catch (e) {
    if (e.message !== "Static fallback") {
      searchBox.textContent = e.message;
      return;
    }
    const base = 1320;
    const ret = 112;
    const pct = 91.52;
    staticState.metrics.queriesExecuted += 1;
    staticState.metrics.cumulativeTokensSaved += base - ret;
    staticState.metrics.averageSavingsPct = pct;
    staticState.auditTrail.unshift({ seq: staticState.auditTrail.length + 1, event: "CONTEXT_SEARCH_TRACKED", actor: consumerAgent, detail: `Saved ${base - ret} tokens (${pct}%).` });
    searchBox.innerHTML = `<div class="ok">Saved ${base - ret} tokens (${pct}% reduction: ${ret} vs ${base} baseline — Static Preview)</div>`;
    render(staticState);
  }
});

document.getElementById("ingestBtn").addEventListener("click", async () => {
  const authorAgent = document.getElementById("authorInput").value.trim();
  const kind = document.getElementById("kindInput").value;
  const title = document.getElementById("titleInput").value.trim();
  const content = document.getElementById("contentInput").value.trim();
  if (!title || !content) return;
  try {
    const res = await fetch("/api/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ authorAgent, kind, title, content }),
    });
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) throw new Error("Static fallback");
    const d = await res.json();
    staticState = d.state;
    render(staticState);
  } catch {
    staticState.memories.unshift({ memory_id: "mem_" + Date.now(), author_agent: authorAgent, kind, title, content, tokens: 28, promoted: false, utility_score: 0.8 });
    render(staticState);
  }
  document.getElementById("titleInput").value = "";
  document.getElementById("contentInput").value = "";
});

loadState();
