# Freight Copilot — Architecture

## Overview

Freight Copilot is a **modular monolith**: all server-side logic lives in a single Python process. The design favours simplicity and auditability over micro-service overhead, which suits a single-operator deployment. A clean internal module boundary is enforced so that individual layers (agents, adapters, API, web) can be replaced or extracted later without cross-cutting rewrites.

```
freight-copilot/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy ORM models (the source of truth for the DB schema)
│   │   ├── schemas/         # Pydantic v2 request/response models and agent I/O contracts
│   │   ├── agents/          # Ten operational agent services (pure Python, no side-effects)
│   │   ├── adapters/        # Exchange + email adapters (TIMOCOM, Trans.eu, IMAP — mock by default)
│   │   ├── api/             # FastAPI JSON routers (v1 REST API consumed by the future Next.js frontend)
│   │   ├── web/             # FastAPI Jinja2 routers that render the MVP server-side dashboard
│   │   └── templates/       # Jinja2 HTML templates (Tailwind via CDN)
│   └── tests/
├── fixtures/                # Synthetic demo seed data (JSON/SQL)
├── frontend/                # Placeholder — Next.js app (roadmap, not yet built)
├── scripts/                 # DB seed script, Makefile helpers
└── docs/
```

---

## Request Flow

### Browser / Dashboard request (server-rendered MVP UI)

```
Browser GET /dashboard
    └─► FastAPI web router (app/web/)
            └─► SQLAlchemy session → DB query
            └─► Agent service (read-only, if enrichment needed)
            └─► Jinja2 template render
    ◄── HTML response
```

### JSON API request (future Next.js or API consumer)

```
Client POST /api/v1/freight/import
    └─► FastAPI API router (app/api/)
            └─► Pydantic v2 schema validation
            └─► Agent service (Intake/Inbox Dispatcher)
            └─► AgentResult returned
            └─► If consequential action → ApprovalRequest created in DB
    ◄── JSON { id, status, approval_request_id? }
```

### Agent invocation (internal only — never called directly by the browser)

```
Agent service called from router
    └─► Reads DB via SQLAlchemy session (dependency-injected)
    └─► Optionally calls LLMProvider (pluggable abstraction)
    └─► Returns AgentResult (structured, validated, never raw LLM text)
    └─► Router persists AgentResult.audit_log entry
    └─► If action_required → creates ApprovalRequest row
```

---

## Database

| Concern | Choice | Rationale |
|---|---|---|
| Default engine | SQLite (single file, `freight.db`) | Zero-config local-first deployment; one forwarder, low concurrency |
| Production option | PostgreSQL via `DATABASE_URL` env var | Drop-in via SQLAlchemy; needed if multi-user or hosted |
| ORM | SQLAlchemy 2.0 (async-compatible mapped classes) | Type-safe, migration-friendly, well-understood |
| Migrations | Alembic | Schema evolution with full audit trail of changes |
| Demo seeding | `scripts/seed_demo.py` reads `fixtures/` | Reproducible demo without network calls |

The `DATABASE_URL` environment variable controls which engine is used. When unset, the application defaults to `sqlite:///./freight.db` relative to the working directory.

---

## Agent Framework

Every agent service follows the same contract:

```python
@dataclass
class AgentResult:
    success: bool
    payload: BaseModel          # agent-specific Pydantic schema
    confidence: float           # 0.0–1.0; deterministic rules → 1.0; LLM → model-reported
    missing_fields: list[str]   # fields the agent could not populate
    action_required: bool       # True → create ApprovalRequest before any external effect
    audit_log: AuditEntry       # timestamp, agent_id, input_hash, output_hash, llm_model_used
    safe_fallback: bool         # True if agent returned default/empty rather than guessing
```

Rules:
- An agent NEVER writes to an external system directly. All external writes go through an `ApprovalRequest`.
- An agent NEVER raises an exception to the caller for recoverable input errors — it returns `success=False` with `missing_fields` populated.
- LLM output is deserialized into the agent's Pydantic response schema; if deserialization fails the agent sets `safe_fallback=True` and returns the empty schema.

### The Ten Operational Agents

| # | Agent | Responsibility |
|---|---|---|
| 1 | Intake / Inbox Dispatcher | Classifies and prioritises incoming freight orders and inquiries |
| 2 | Freight Opportunity Scout | Scans exchange data for matching load/truck offers |
| 3 | Pricing & Margin | Calculates proposed buy/sell rates and expected margin |
| 4 | Carrier Matching | Ranks available carriers for a freight order |
| 5 | Carrier Risk & Verification | Assesses carrier reliability and document status |
| 6 | Communication Drafting | Drafts emails and messages in PL/EN/IT/DE |
| 7 | Transport Monitoring | Tracks active shipments, detects delays, raises alerts |
| 8 | Document Controller | Validates transport documents (CMR, invoices, POD) |
| 9 | Personal Operational Knowledge Base | Stores and retrieves operational knowledge and past decisions |
| 10 | Compliance & Safety Supervisor | Cross-checks actions against rules (cabotage, ADR, driver hours) |

---

## LLM Provider Abstraction

```
LLMProvider (abstract base)
    ├── DeterministicProvider   ← default (no external calls, rule-based)
    ├── MockProvider            ← used in tests (scripted responses)
    ├── LocalOpenAIProvider     ← placeholder for local OpenAI-compatible endpoint
    └── AnthropicProvider       ← placeholder; enabled via ANTHROPIC_LLM_ENABLED=true
                                   primary model:   claude-opus-4-8
                                   subagent model:  claude-sonnet-4-6
```

The product is **fully operational with `DeterministicProvider`**. Enabling an LLM provider changes the quality of natural-language outputs (drafts, summaries) but does not change any data flow or safety guarantees. LLM output is always validated against the agent's Pydantic schema before use. LLM output never directly triggers an external write.

---

## Adapter Layer

```
ExchangeAdapter (abstract base)
    ├── TimocomAdapter          ← wraps official TIMOCOM API (disabled by default)
    │       MockTimocomAdapter  ← returns fixture data; used when TIMOCOM_ENABLED=false
    └── TransEuAdapter          ← wraps official Trans.eu API (disabled by default)
            MockTransEuAdapter  ← returns fixture data; used when TRANSEU_ENABLED=false

EmailAdapter (abstract base)
    ├── ImapEmailAdapter        ← connects to IMAP mailbox (disabled by default)
    └── MockEmailAdapter        ← returns fixture emails; used when EMAIL_ENABLED=false
```

All adapters expose an identical Python interface. The active implementation is resolved at startup from feature flags. No scraping, browser automation, or CAPTCHA bypass is used. Only official API interfaces are called when real adapters are enabled.

**External reads** (fetching data from exchanges) are separately gated by `EXTERNAL_READS_ENABLED`.
**External writes** (publishing, bidding, messaging via APIs) are separately gated by `EXTERNAL_WRITES_ENABLED` and require a human-approved `ApprovalRequest` even when the flag is true.

---

## ApprovalRequest Flow

Every consequential external action must pass through the ApprovalRequest lifecycle before it can be executed.

```
Agent produces action_required=True
        │
        ▼
  ApprovalRequest row created in DB
  (status=PENDING, action_type, payload_json, agent_id, created_at)
        │
        ▼
  Human reviewer sees request in Approval Inbox (/approvals)
        │
        ├──[APPROVE]──► adapter.execute(payload)  ← actual external call (if writes enabled)
        │                       │
        │               ExternalActionLog row written (success/failure, timestamp, response_hash)
        │
        └──[REJECT]───► ApprovalRequest status=REJECTED, rejection_reason stored
                        No external call made.

At all times:
  EXTERNAL_WRITES_ENABLED=false  →  adapter.execute() is a no-op that logs "dry-run"
```

ApprovalRequest statuses: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `EXECUTED`, `EXECUTION_FAILED`.

---

## Audit and Traceability

Every agent invocation appends an `AuditEntry` row:

| Column | Content |
|---|---|
| `id` | UUID |
| `agent_id` | string slug of the agent |
| `triggered_by` | user session id or `"system"` |
| `input_hash` | SHA-256 of serialized input (not the raw input, to keep PII out of logs) |
| `output_hash` | SHA-256 of serialized AgentResult.payload |
| `confidence` | float from AgentResult |
| `llm_model_used` | model id string or `null` |
| `duration_ms` | wall-clock time |
| `created_at` | UTC timestamp |

The full input and output payloads are stored in the `agent_invocation_detail` table (separate, larger rows) and linked by `audit_entry_id`. This allows the audit trail to be retained at low storage cost while detailed payloads can be pruned on a schedule.

---

## Security and Prompt-Injection Defence

All content ingested from external sources (freight exchange data, emails, PDFs, pasted text) is treated as **untrusted data**. It is stored as opaque strings and passed to agents only through typed schema fields. Agent system prompts are never constructed by concatenating raw user-supplied text. The LLM provider wrapper enforces a boundary: structured JSON schema output is requested; the response is parsed with strict Pydantic validation; any deviation causes `safe_fallback=True` rather than executing the unexpected content.
