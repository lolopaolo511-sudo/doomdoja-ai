# Freight Copilot — Product Scope

## Business Context

A **road-freight forwarder** (Polish: *spedycja*) earns its living by buying transport capacity from external carriers and selling transport service to customers. The company does not own trucks. Every order is fulfilled by negotiating with carriers on freight exchanges (TIMOCOM, Trans.eu) or from a curated carrier directory. Margin is the difference between the rate charged to the customer and the rate paid to the carrier.

The operational bottleneck is human attention: a single forwarder handles tens of active transports simultaneously, monitors delays, chases documents, answers emails in multiple languages, and stays within compliance rules — all in real time. Freight Copilot is a **local-first, human-in-the-loop decision-support and workflow-automation tool** that extends the capacity and consistency of that one operator.

### Operating Context

| Parameter | Value |
|---|---|
| Geography | European road freight |
| Languages | Polish, English, Italian, German |
| Currencies | EUR and PLN |
| Timezone | Europe/Warsaw |
| Deployment | Local machine (single operator); server deployment is possible |
| Exchanges used | TIMOCOM, Trans.eu |
| Truck ownership | None — capacity always purchased externally |

---

## What Freight Copilot Does: The Ten Capabilities

### 1. Intake and Inbox Dispatching

Classifies, deduplicates, and prioritises incoming freight orders and inquiries from email, manual import, and (when enabled) exchange APIs. Surfaces the highest-value opportunities first. Drafts an initial action plan for each item.

### 2. Freight Opportunity Scouting

Scans available freight and truck offers on connected exchanges, matches them against open orders, and presents ranked candidates. Filters by route corridor, load type, required dates, and estimated margin.

### 3. Pricing and Margin Calculation

Proposes a buy rate (to pay the carrier) and a sell rate (to charge the customer) for a given route and load. Calculates expected margin. Uses rule-based pricing models by default (no live market data required). Flags orders where margin is below a configurable threshold.

### 4. Carrier Matching

Ranks carriers in the directory for a specific freight order based on route fit, equipment type, past performance, and current availability. Produces a shortlist with reasoning the operator can act on.

### 5. Carrier Risk and Verification

Checks a carrier's document status (licence, insurance, certificates) and reliability history. Raises alerts when documents are approaching expiry or when a carrier's recent track record is poor. Does not approve carriers — it surfaces the evidence for the operator to decide.

### 6. Communication Drafting

Drafts emails and messages to carriers and customers in Polish, English, Italian, or German. Covers rate enquiries, order confirmations, delay notifications, and document requests. All drafts require operator review before sending.

### 7. Transport Monitoring

Tracks the status of active shipments. Compares reported positions and ETAs against planned schedules. Detects and alerts on delays, missed check-ins, and loading/unloading time overruns. Does not contact carriers autonomously.

### 8. Document Control

Checks completeness of transport documentation: CMR consignment notes, invoices, proof of delivery (POD), carrier certificates. Identifies missing or expiring documents, flags discrepancies, and prompts the operator to request what is missing.

### 9. Personal Operational Knowledge Base

Stores and retrieves the operator's accumulated knowledge: lane-specific rate history, carrier notes, customer preferences, past decisions and their outcomes. Makes institutional knowledge searchable and reusable.

### 10. Compliance and Safety Supervision

Cross-checks planned and active transports against regulatory constraints: cabotage rules, ADR hazardous goods requirements, driving hours (EC 561/2006), and company-specific policies. Raises a blocking alert if a constraint is violated before the operator approves an action.

---

## What Freight Copilot Explicitly Does NOT Do

These are non-negotiable safety boundaries enforced at the architecture level, not configuration:

| Prohibited action | Why it is prohibited |
|---|---|
| Accept or reject a freight order on an exchange autonomously | Legally binding commercial commitment |
| Publish a freight or truck offer on an exchange | Creates public market offer binding on the company |
| Place or withdraw a bid on an exchange | Binding commercial act |
| Send an email or message without operator approval | Creates contractual or pre-contractual obligations |
| Confirm a rate to a customer or carrier | Binding price agreement |
| Conclude or sign a transport contract | Legal commitment |
| Change loading, unloading, or delivery dates | Operational commitment with liability implications |
| Issue, validate, or legally approve an invoice | Financial and legal instrument |
| Approve a carrier as legally compliant | Liability for subcontractor qualification |
| Mark a transport document as legally valid | Legal certification |
| Scrape TIMOCOM or Trans.eu via browser automation | Violates platform ToS; brittle; security risk |
| Bypass CAPTCHAs on any platform | Violates ToS and potentially applicable law |

Every action in the above list, if initiated by the system, results in an **ApprovalRequest** that must be reviewed and approved by a human operator before any external call is made. Even then, external writes are disabled by default (`EXTERNAL_WRITES_ENABLED=false`).

---

## Target User

One road-freight forwarder operating without company-owned trucks. The user is the operator: they read agent outputs, review approval requests, approve or reject proposed actions, and remain legally and commercially responsible for every decision. Freight Copilot extends the operator's capacity — it does not replace their judgment.

---

## MVP vs Later

### MVP (Built)

- Server-rendered Jinja2 + Tailwind dashboard (Python/FastAPI)
- All ten agents running in deterministic (rule-based) mode
- Mock adapters for TIMOCOM and Trans.eu (fixture data)
- SQLite database, single-user
- One-command start: `make demo`
- Full ApprovalRequest workflow (create, review, approve, reject)
- Audit log for every agent invocation
- Demo seed data covering all five core workflows

### Roadmap (Not Yet Built)

- Real TIMOCOM and Trans.eu API adapters (official APIs, no scraping)
- IMAP email integration
- Next.js + TypeScript + React production frontend (replaces Jinja2 dashboard)
- Multi-user support with role-based access
- PostgreSQL as the primary database for hosted/multi-user deployments
- LLM-powered agents (Anthropic and local OpenAI-compatible endpoints)
- Semantic retrieval with pgvector for the Knowledge Base
- Live pricing intelligence from market rate feeds
- GPS/ETA tracking integration for Transport Monitoring
