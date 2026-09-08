# ORELIUS Ecosystem Architecture — Autonomous 1,000+ Touchpoint Engine

> One company of AI agents, not four separate projects.
> **ORELIUS** = executive brain · **ATHENA** = social operations · **HIGGBOT** = creative studio · **LUCIUS** = owner interface.
>
> North Star: **maximize qualified conversations & business opportunities per 1,000 meaningful touchpoints** — never raw message volume, never fake engagement, never platform circumvention.

This document is the internal architecture map (directive Phase 0) plus the phased build plan. It is kept current as phases land.

---

## Phase 0 — Audit of the existing ecosystem (verified from source)

### ORELIUS — `anthony380morales-ops/orelius` (this repo)
FastAPI + Python + Postgres (Neon), deployed on Render; brain = Claude Haiku 4.5.
- `backend/app/core/oreilus_engine.py` — the coordinating engine (Claude, memory, security, intent routing: ATHENA delegation, NXG leads, live finance news, hot-topic reels). **Preserved and extended — not replaced.**
- `core/claude_client.py` (chat, tools, web search), `memory_manager.py`, `security.py`, `prompts.py`, `token_optimizer.py`, `shared_memory.py` (Postgres `/api/memory` hub — the ORELIUS⇄LUCIUS⇄ATHENA bus).
- Automations: `core/finance_intel.py` (cited economic news), `core/nxg_intel.py` (Supabase leads + traffic), `core/hot_topic.py` (reels).
- API routes: `chat`, `system`, `auth`, `memory`, `automation`. Scheduler via external cron hitting secured endpoints.

### ATHENA — `anthony380morales-ops/ATHENA`  (Node/TS, runs on owner's machine, localhost:8787)
Social operations + execution. HTTP surface (`src/server/http.ts`):
`POST /jobs {action}` (once·autopilot·batch·research·brief) · `GET /jobs/:id` · `POST /design {prompt}` · `POST /site {prompt}` · `GET /status` · `GET /health`.
Modules: `pipeline/` (cli, cron), `design/`, `publish/` (later, ig-graph, r2), `research/` (viralfindr), `guardrails/`, `db/` (drizzle + sqlite). Bridged to ORELIUS today via the shared-memory `design_request` → `design_result` pattern (`integrations/athena/athena_orelius_bridge.py`).

### HIGGBOT — `anthony380morales-ops/higgbot`  (Node/TS, MCP over stdio)
Provider-agnostic **design engine** ("does what Higgsfield does") — the owner's own creative core, **not** Higgsfield the vendor. Exposes `design.*` MCP tools. 6 layers: planner → registry → router (cheapest-capable-first + budget cap + escalation) → adapters (fal.ai/Google/Recraft/local/…) → job+asset store (per-client cost) → finishing. **Has a built-in simulation mode** ($0 placeholder assets with no keys). Driven by ATHENA/LUCIUS.

### LUCIUS — `anthony380morales-ops/lucius-agent`  (Python, LiveKit)
Owner's personal assistant / human interface: `agent.py`, `tools.py`, `memory/`, `prompts.py`, `notifications.py`, `self_repair.py`, `security/`. Voice + realtime. Connected to ORELIUS through the shared-memory bus. **Stays the interface — not the orchestration brain.**

---

## Target architecture

```
OWNER → LUCIUS → ORELIUS ──┬── INTELLIGENCE SUBAGENTS ──┐
                           └── STRATEGY ENGINE ─────────┤
                                                        ▼
                                                MISSION PLANNER → MISSION QUEUE → ATHENA
                                                                                   ├── Instagram
                                                                                   └── Facebook
                                                                                        │
   ORELIUS ← LEARN/OPTIMIZE ← PERFORMANCE DATA ← CONVERSATION DATA ────────────────────┘
```
Creative path: `ORELIUS → content mission → ATHENA → HIGGBOT → asset → ATHENA QA → publish`.
Messaging path: `social event → ATHENA/Manychat → classifier → ORELIUS strategy → ATHENA execute → {QUALIFIED · NURTURE · HUMAN HANDOFF · DO NOT CONTACT}`.

Agents cooperate through **typed contracts (mission packets)**, not shared prompts.

---

## Contracts (stable interfaces)

| Contract | Owner | Consumers | Status |
|---|---|---|---|
| **MissionPacket** (`app/orchestration/mission.py`) | ORELIUS | ATHENA, HIGGBOT (via ATHENA) | ✅ Phase 1 |
| **Agent registry** (`app/orchestration/agent_registry.py`) | ORELIUS | ORELIUS planner | ✅ Phase 1 (declarations) |
| **Messaging humanization policy** (`app/orchestration/messaging_policy.py`) | ORELIUS | every autonomous message channel | ✅ Phase 1 |
| **Kill switches / run-mode** (`app/orchestration/flags.py`) | ORELIUS | all executors | ✅ Phase 1 |
| **Mission queue** (`app/orchestration/mission_queue.py`) | ORELIUS | ORELIUS planner/workers | ✅ Phase 2 |
| **ATHENA adapter** (`/ecosystem/athena/*`) | ORELIUS | ORELIUS | ✅ Phase 3 (simulation-first) |
| **HIGGBOT creative contract** (`app/orchestration/creative.py`, `/ecosystem/higgbot/*`) | ORELIUS → ATHENA → HIGGBOT | ORELIUS | ✅ Phase 4 (simulation-first) |
| **LUCIUS control surface** (`app/orchestration/control.py`, `/ecosystem/control/*`, `/ecosystem/lucius/*`) | LUCIUS ↔ ORELIUS | LUCIUS (voice) | ✅ Phase 5 |

**Absolute messaging rule (live now):** no autonomous message may ever contain `--`. Enforced by `messaging_policy.enforce()` (validate → regenerate → sanitize backstop). The single em-dash `—` is allowed.

---

## Guardrails baked in from Phase 1

- **Simulation-first.** `SOCIAL_AUTOMATION_MODE=simulation` is the default; `SYSTEM_PAUSE` forces simulation regardless. No real message/publish/spend until explicitly set to `live` **and** no pause flag is set.
- **Compliance gate.** A mission may only reach an executor once `compliance.status == approved` (`MissionPacket.is_ready_for_executor()`). When in doubt → block/escalate.
- **Kill switches.** `SYSTEM_PAUSE, MESSAGING_PAUSE, PUBLISHING_PAUSE, OUTBOUND_PAUSE, NXG_PAUSE, IBC_PAUSE, HIGGBOT_PAUSE, ATHENA_PAUSE` — durable in `system_flags`, checkable from API/dashboard/LUCIUS.
- **No fake anything.** No fake accounts/engagement, no scraping private data, no credential bypass, no platform circumvention. Where an action can't be legally/technically automated it becomes a structured opportunity for human/ATHENA review.
- **Two brands, never merged.** NXG (California consumers) vs IBC (professionals) carry distinct voice, audience, and destination.

---

## Phased build plan (test at every gate)

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Architecture audit + map | ✅ done |
| 1 | Mission protocol · agent registry · messaging guardrail · kill switches · run-mode · DB spine | ✅ **this change** (12/12 tests) |
| 2 | Durable mission queue (Postgres): retries, backoff, dead-letter, priority, dedupe, states, expiry | ✅ **this change** (13/13 tests) |
| 3 | ATHENA adapter (`/ecosystem/athena/*`) over the existing job API, simulation-first | ✅ **this change** (13/13 tests) |
| 4 | HIGGBOT creative contract (via ATHENA, simulation-first, budget-capped) | ✅ **this change** (10/10 tests) |
| 5 | LUCIUS control surface (status, pause/resume by scope, approvals, handoffs, owner alerts) | ✅ **this change** (8/8 tests) |
| 6 | Economic intelligence + financial impact agents + intelligence→mission planner (reuse `finance_intel`/`hot_topic`) | ✅ **this change** (8/8 tests) |
| 7 | Audience-intelligence (reuses live NXG lead concerns) + social-opportunity agents (compliant slate, live discovery gated) | ✅ **this change** (8/8 tests) |
| 8 | Conversation intelligence (state machine, strategist w/ `--`-safe drafts, prospect memory, human handoff) | ✅ **this change** (12/12 tests) |
| 9 | Compliance/risk engine (mandatory reviewer) | ⏳ |
| 10 | Touchpoint allocation engine (adaptive, outcome-driven) | ⏳ |
| 11 | Performance feedback + analytics tables | ⏳ |
| 12 | Adaptive optimization (params/prompts/routing only — never source) | ⏳ |
| 13 | North-Star dashboard | ⏳ |
| 14 | End-to-end simulation acceptance test (§69) | ⏳ |
| 15 | Production activation (per-provider, credential-gated) | ⏳ |

Each later phase is additive, preserves existing behavior, and ships with tests. Phases 3–5 and 15 require owner-provided credentials/endpoints (ATHENA token, HIGGBOT MCP path, LUCIUS URL, Manychat/Meta/n8n) — the adapters ship with a simulation fallback so the pipeline is testable before any real credential exists.
