# MekoMemoir — Multi-Agent Shared Context & Token Efficiency Copilot

Submission for **ContextCon: Remember Everything** on HackerEarth (`$10,000 USD` Prize Pool — **Theme: Token Efficiency & Best Auditability**).

## How MekoMemoir Uses Meko Context Engine (`YugabyteDB / Meko`)
1. **Live Meko Cloud Health & Adapter (`MekoCloudClient`)**: Connects to `https://api.mekodata.ai/api/v1/health`, Datapack REST API (`POST /datapacks`, `POST /promote-memories`), and MCP Server (`https://mcp.mekodata.ai/mcp`) using mandatory `Authorization: Bearer mko_tkn_...` and `User-Agent` headers.
2. **Token Efficiency Measurement (`retrieve_context_and_measure`)**: Compares baseline full-history replay against ranked Meko `context_search` slices, computing real-time **tokens saved** and **savings %** (`track_token_usage`).
3. **Self-Learning Promotion Loop (`promote_memory`)**: Promotes verified high-utility lessons to the durable Knowledge Base (`promoted = True`), boosting retrieval precision across future agents (`PlannerAgent`, `CoderAgent`, `SecurityAgent`, `ReviewerAgent`).
4. **Full Audit Trail (`Show Your Work`)**: Every memory ingestion, promotion, and context retrieval query is logged with content hashes and token telemetry.

## Run & Test Locally
```bash
python -m unittest discover -s tests -v
python backend/server.py
# Open http://127.0.0.1:8095
```
