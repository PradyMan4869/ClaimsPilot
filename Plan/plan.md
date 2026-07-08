# ClaimsPilot — Implementation Plan

## Goal
Three single-responsibility agents processing insurance claims end-to-end, wired
together by the **A2A protocol** (not function calls). Each agent is an independent
HTTP service publishing an Agent Card at `/.well-known/agent-card.json`; the
orchestrator discovers and delegates via A2A JSON-RPC. Kill any agent and the others
still stand — that is the interoperability argument A2A makes over monolithic graphs.

## Architecture

```
                         ┌────────────────────────────┐
                         │         Gradio UI          │
                         │ upload claim → live agent  │
                         │ log → decision + audit     │
                         └─────────────┬──────────────┘
                                       │
                         ┌─────────────▼──────────────┐
                         │  Orchestrator (A2A client) │──── LangSmith traces
                         └───┬──────────┬──────────┬──┘     (full chain + handoffs)
                     A2A     │          │          │    A2A
                 message/send│          │          │message/send
              ┌──────────────▼─┐ ┌──────▼───────┐ ┌▼───────────────┐
              │ Agent 1        │ │ Agent 2      │ │ Agent 3        │
              │ EXTRACTOR      │ │ VALIDATOR    │ │ RESPONDER      │
              │ :8101          │ │ :8102        │ │ :8103          │
              │ doc → fields   │ │ CrewAI crew: │ │ decision →     │
              │ (LM Studio)    │ │  policy look │ │ accept/reject/ │
              │                │ │  up + rules  │ │ escalate letter│
              └────────────────┘ │  engine      │ └────────────────┘
                                 └──────┬───────┘
                                   MCP (stdio)
                                 ┌──────▼───────┐
                                 │ Policy MCP   │──► MongoDB (policies, rules)
                                 │ server       │
                                 └──────────────┘
```

## Modules

| Module | Responsibility |
|---|---|
| `common/config.py` | Env-driven settings (ports, LM Studio, Mongo, LangSmith) |
| `common/schemas.py` | Pydantic contracts: `ExtractedClaim`, `ValidationResult`, `ResponseLetter` — the A2A payloads |
| `common/llm.py` | LM Studio client (OpenAI-compatible), JSON-mode helper |
| `a2a_lib/models.py` | A2A v1.0 types: AgentCard, AgentSkill, Message, Text/Data parts, JSON-RPC envelope |
| `a2a_lib/server.py` | FastAPI factory: serves the agent card + `message/send` endpoint around a handler fn |
| `a2a_lib/client.py` | httpx client: card discovery + `send_data()` |
| `agents/extractor/` | LLM structured extraction from claim text (port 8101) |
| `agents/validator/` | CrewAI crew (policy-lookup task + rules-engine task); tools call MongoDB via MCP (port 8102) |
| `agents/responder/` | Drafts accept/reject/escalate letter with reasoning chain (port 8103) |
| `mcp_server/policy_server.py` | FastMCP (stdio): `get_policy`, `get_validation_rules` over MongoDB |
| `db/policies.py` | Mongo repository + in-memory fallback so the demo runs without Mongo |
| `orchestrator/pipeline.py` | A2A client chain, emits step events for the UI, LangSmith-traced |
| `scripts/generate_claims.py` | Synthetic claim documents via the LLM (template fallback), 50–100 docs |
| `scripts/seed_policies.py` | Seed MongoDB with policies + rules matching the synthetic claims |
| `scripts/start_agents.py` | Launch all three agent servers as subprocesses |
| `ui/app.py` | Gradio: upload PDF/TXT → streaming step log → decision + audit trail |
| `tests/` | Contracts, A2A round-trip (in-process ASGI), rules engine, extractor parsing |

## Key design decisions
1. **A2A implemented per spec, transparent and dependency-light** — agent card at the
   well-known URI, JSON-RPC 2.0 `message/send`, `DataPart` for structured payloads.
   Every agent is independently startable/killable; the orchestrator only knows URLs.
2. **CrewAI scoped inside Agent 2** — sub-tasks (policy lookup, rules evaluation) are
   CrewAI tools; a `CREWAI_ENABLED=false` fallback runs the same tools deterministically
   so validation is testable and demo-safe without an LLM.
3. **Rules engine is deterministic code, not LLM** — coverage window, covered incident
   types, limits, waiting period. The LLM narrates; it does not decide coverage.
4. **Decision space**: `approve` (all checks pass, amount ≤ auto-approve threshold),
   `reject` (hard rule violated), `escalate` (passes rules but exceeds threshold or
   low extraction confidence).
5. **Synthetic data as a feature** — generation script is part of the deliverable.

## Build order
1. common (config/schemas/llm) → 2. a2a_lib → 3. db + MCP server → 4. agents 1–3 →
5. orchestrator → 6. scripts → 7. UI → 8. tests

## Definition of done
- `python scripts/seed_policies.py` + `python scripts/generate_claims.py` produce data
- `python scripts/start_agents.py` brings up 3 A2A servers; each serves its agent card
- `python ui/app.py` processes an uploaded claim end-to-end with a live step log
- `pytest` green without any external service running
