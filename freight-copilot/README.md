# 🚚 Freight Copilot

A **local-first, human-in-the-loop** decision-support and workflow-automation
tool for a road-freight forwarder (*spedycja*) working **without its own
trucks** — it finds freight opportunities, evaluates them, shortlists external
carriers, drafts communication, and monitors active transports. It is built to
sit alongside freight exchanges such as **TIMOCOM** and **Trans.eu** via
official API adapters (mocked in this MVP), never via scraping.

> **The forwarder stays in control.** The system never accepts, rejects,
> publishes, bids, sends, or signs anything on its own. Every consequential
> external action becomes an **ApprovalRequest** a human must review.

## Quick start (one command)

```bash
cd freight-copilot
make demo
# → builds a venv, installs deps, seeds demo data (SQLite), serves the app
# → open http://127.0.0.1:8000
```

No Docker, Postgres, Node, or external API account is required for the demo.
(`make test` runs the suite; `docker compose up` runs a Postgres-backed stack.)

## What you'll see

| Page | What it shows |
|------|---------------|
| **Dashboard** | New opportunities, urgent queue, high scores, delayed transports, alerts, pending approvals, integration health |
| **Opportunity Inbox** | Paste a freight offer (PL/EN/IT/DE) → normalized fields, missing data, score |
| **Freight Detail** | Source text, structured data, opportunity score breakdown, pricing & margin, carrier shortlist with risk flags, suggested questions |
| **Carrier Directory** | Lanes, vehicles, capabilities, reliability, risk |
| **Active Transports** | Timeline, alerts (e.g. pickup delay), document completeness |
| **Approval Inbox** | Proposed external actions — approve (simulated in demo) / reject |
| **Documents** | Operational completeness checks (never legal validation) |
| **Knowledge Base** | Searchable operational notes with provenance; suggested notes need approval |
| **Settings** | Feature flags, integrations, defaults |

## Safety model (non-negotiable)

- **External writes disabled by default**; demo approvals are *simulated*.
- **No scraping / browser automation** of TIMOCOM or Trans.eu — official API
  adapters with mock implementations + manual import only.
- **All imported content is untrusted data**, scanned for prompt injection and
  never executed as instructions.
- **Traceability**: every agent run, recommendation, and decision is audited;
  estimates are labelled estimates, never facts.
- **Secrets** live in `.env` (git-ignored) and are redacted from logs.

## Architecture (modular monolith)

```
backend/app/
  models.py        domain model (offers, carriers, shipments, approvals, audit…)
  agents/          10 operational agents (rule-based + optional LLM provider)
  adapters/        TIMOCOM / Trans.eu / email + provider interfaces (mock/disabled/official)
  api/routes.py    JSON API (/api/*)
  web/             server-rendered dashboard (Jinja2 + Tailwind)
  services.py      orchestration shared by API + UI
  seed.py          realistic multilingual demo data
```

See [`docs/`](docs/) for architecture, security, threat model, integration
checklists, the demo guide, the runbook, assumptions, and the list of
questions to ask the employer before enabling real integrations.

## Tech

Python 3.11+ · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite (Postgres
optional) · Jinja2 + Tailwind. Production front-end (Next.js) is on the roadmap.

## Development with Claude Code subagents

`.claude/agents/` defines specialised subagents (backend, frontend, agent-
workflow, integration, security, QA, docs). The orchestrator runs on
`claude-opus-4-8`; implementation subagents on `claude-sonnet-4-6`. The LLM
layer is entirely optional — the product is fully functional with the
deterministic provider.
