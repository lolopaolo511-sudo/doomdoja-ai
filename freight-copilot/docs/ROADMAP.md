# Freight Copilot — Roadmap

The roadmap is divided into phases. Each phase has a clear entry condition (what must be true before starting) and a defined exit condition (what "done" means). Features within a phase are listed in priority order.

---

## Phase 0 — Foundation (MVP, Built)

**Entry condition:** Project scaffolded, frozen architecture agreed.
**Exit condition:** `make demo` works end-to-end; all five core workflows exercisable in the browser; no external dependencies required.

### What is built

- Modular monolith: FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2
- Server-rendered Jinja2 + Tailwind dashboard (all nine UI pages)
- All ten operational agents running with `DeterministicProvider` (rule-based, no LLM calls)
- Mock adapters for TIMOCOM and Trans.eu (fixture data, no network calls)
- Mock email adapter (fixture inbox, no IMAP connection)
- Full ApprovalRequest workflow: create → human review → approve/reject
- Audit log: every agent invocation recorded with confidence, duration, input/output hashes
- Demo seed data in `fixtures/`: synthetic carriers, freight orders, transports, documents
- One-command start: `make demo`
- Feature flags for every external integration (all `false` by default)
- Unit tests for all agent logic; integration tests for key API routes
- Prompt-injection defence: all imported content treated as untrusted data

### What is explicitly out of scope for this phase

- Real exchange API calls
- Real email sending or receiving
- Any LLM calls
- Multi-user access control
- Production-grade deployment configuration

---

## Phase 1 — Real Data Reads (Enable Exchange Adapters, Read-Only)

**Entry condition:** MVP validated by operator through daily use; TIMOCOM and/or Trans.eu API credentials obtained; official API documentation reviewed.
**Exit condition:** Operator can see live freight and truck offers from at least one exchange inside Freight Copilot without leaving the tool.

### Features

1. Implement `TimocomAdapter` against official TIMOCOM API (read operations only)
2. Implement `TransEuAdapter` against official Trans.eu API (read operations only)
3. Set `EXTERNAL_READS_ENABLED=true`, `TIMOCOM_ENABLED=true` / `TRANSEU_ENABLED=true` in operator's `.env`
4. Rate-limit and retry logic in adapters; graceful fallback to mock on API errors
5. Data normalisation: map exchange-specific field names to internal schemas
6. Opportunity Scout agent consumes live data instead of fixtures
7. Sync job: periodic pull of new offers into local DB (configurable interval)
8. UI: distinguish live data from demo data with a clear visual indicator

### What remains disabled

- External writes (`EXTERNAL_WRITES_ENABLED` stays `false`)
- Email integration
- LLM calls

---

## Phase 2 — Email Integration

**Entry condition:** Phase 1 complete and stable; operator's IMAP/SMTP credentials available.
**Exit condition:** Operator's inbox is visible inside Freight Copilot; Intake agent processes real emails; Communication agent drafts can be reviewed and sent.

### Features

1. Implement `ImapEmailAdapter` (OAuth2 or app-password; Microsoft Graph as fallback for O365)
2. Implement `SmtpEmailAdapter` for outbound (all sends go through ApprovalRequest)
3. Set `EMAIL_ENABLED=true`
4. Intake / Inbox Dispatcher processes real emails: classify, deduplicate, prioritise
5. Communication Drafting agent: drafted replies appear in Approval Inbox before any send
6. Thread linking: emails linked to freight orders and transports
7. Attachment handling: PDFs routed to Document Controller agent

### What remains disabled

- Exchange writes
- LLM calls (optional — can be enabled independently in this phase)

---

## Phase 3 — LLM-Assisted Agents (Optional Enhancement)

**Entry condition:** Phase 0 or later; operator wants better draft quality and richer classification. Can be enabled independently of Phases 1 and 2.
**Exit condition:** LLM-powered agents produce noticeably better outputs than deterministic versions on the operator's real workload; all safety invariants still hold.

### Features

1. Implement `AnthropicProvider` (primary: `claude-opus-4-8`; subagents: `claude-sonnet-4-6`)
2. Implement `LocalOpenAIProvider` for operators who prefer a local model endpoint
3. Set `ANTHROPIC_LLM_ENABLED=true` (or `LOCAL_LLM_ENABLED=true`) and supply API key
4. Communication Drafting: multilingual drafts (PL/EN/IT/DE) with context from KB
5. Intake Dispatcher: richer classification using email body and attachment content
6. Freight Opportunity Scout: semantic matching beyond rule-based filters
7. Pricing agent: natural-language explanation of rate recommendation
8. All LLM outputs validated against Pydantic schemas; `safe_fallback=True` on any parse failure
9. Prompt-injection hardening audit: review all prompts that touch user-supplied content

---

## Phase 4 — Production Frontend (Next.js)

**Entry condition:** Core product validated; operator wants richer UI (mobile, keyboard shortcuts, real-time updates); or team size grows beyond one.
**Exit condition:** Next.js frontend replaces the Jinja2 dashboard for day-to-day use; Jinja2 dashboard retained as a fallback for diagnostics.

### Features

1. Next.js 14+ app (TypeScript, React, Tailwind) in `frontend/`
2. Consumes the existing FastAPI JSON API (`/api/v1/`)
3. Real-time transport status updates via WebSocket or SSE
4. Keyboard-driven approval workflow (approve/reject without mouse)
5. Mobile-responsive layout for on-the-go monitoring
6. Dark mode
7. Jinja2 dashboard demoted to `/internal/` path, retained for debugging

---

## Phase 5 — Multi-User and Role-Based Access

**Entry condition:** Second operator or assistant needs access; or tool is offered as a service to multiple forwarders.
**Exit condition:** Multiple named users can log in; each action is attributed to a user; data is scoped appropriately.

### Features

1. User model with authentication (email + password or SSO)
2. Role definitions: `operator` (full access), `assistant` (create/draft, no approve), `read-only`
3. All AuditEntry rows attributed to the authenticated user
4. Session management (JWT or server-side sessions)
5. Per-user notification preferences
6. Migration from SQLite to PostgreSQL as the default engine (required for multi-user writes)
7. Alembic migration from single-user schema to multi-user schema

---

## Phase 6 — Semantic Retrieval and Pricing Intelligence

**Entry condition:** Knowledge Base has accumulated meaningful history (typically 3–6 months of real use); operator wants smarter retrieval and pricing.
**Exit condition:** Knowledge Base answers "have we done this lane before?" with semantic similarity; pricing agent uses historical actuals rather than only static bands.

### Features

1. Migrate to PostgreSQL with `pgvector` extension enabled
2. Knowledge Base: embed past decisions, lane notes, and carrier comments; retrieve by cosine similarity
3. Pricing agent: retrieve comparable historical lanes; adjust proposal based on actuals
4. Freight Opportunity Scout: semantic route matching beyond exact geo-match
5. Document Controller: semantic matching of document templates to incoming PDFs
6. Embedding model: local (e.g., sentence-transformers) or API-based (Anthropic / OpenAI embeddings)

---

## Phase 7 — Live Tracking and Proactive Alerting

**Entry condition:** Transport Monitoring has identified a reliable tracking data source (carrier-provided ETA links, telematics API, or project44/FourKites integration).
**Exit condition:** Delay alerts are raised automatically from real GPS/ETA data; operator does not need to manually check in on every active transport.

### Features

1. `TrackingAdapter` abstraction with mock implementation
2. Integration with at least one tracking data source (TBD)
3. Set `TRACKING_ENABLED=true`
4. Transport Monitoring agent: automated ETD/ETA comparison; alert on deviation > configurable threshold
5. Proactive Communication Drafting: draft customer delay notification when alert fires (human approval required before sending)
6. Transport timeline visualisation in the dashboard

---

## Summary Table

| Phase | Theme | Key Dependency | External Calls |
|---|---|---|---|
| 0 (MVP) | Foundation | None | None |
| 1 | Live exchange reads | API credentials | Reads only |
| 2 | Email integration | IMAP/SMTP credentials | Reads + approved sends |
| 3 | LLM assistance | API key or local model | LLM API only |
| 4 | Production frontend | Phase 0+ | None new |
| 5 | Multi-user | Phase 4 + Postgres | None new |
| 6 | Semantic retrieval | Phase 5 + pgvector | Embedding API (optional) |
| 7 | Live tracking | Tracking data source | Tracking API reads |
