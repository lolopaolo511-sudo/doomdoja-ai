# Security Model & Controls

## Overview

Freight Copilot is a local-first, human-in-the-loop decision-support tool. The security model is designed around three principles:

1. **No autonomous external action** — every consequential external write requires a human-reviewed ApprovalRequest before execution.
2. **Defense in depth** — multiple independent controls protect the same surface; a single misconfiguration does not cause a breach.
3. **Untrusted-data discipline** — all imported content (freight text, emails, PDFs, platform data) is treated as data, never as instructions.

---

## 1. Secrets Management

### .env and .env.example

- All credentials, API keys, and sensitive configuration values are stored in a `.env` file that is **never committed to version control** (confirmed via `.gitignore`).
- A `.env.example` file ships with the repository, listing every expected variable with placeholder or empty values and explanatory comments. It contains no real credentials.
- At startup, the application validates the presence of required variables and fails fast with a non-revealing error if any are missing.

### Secret Redaction in Logs

- A log-sanitization middleware strips known secret patterns (API keys, tokens, passwords, database connection strings) from all structured log output before it is written.
- Log formatters are configured to never serialize `Authorization` headers, `Cookie` headers, or any field whose key contains `key`, `token`, `secret`, `password`, or `credential` (case-insensitive).
- Stack traces that may contain request context are passed through the same sanitizer before emission.

### No Secrets in Frontend Payloads

- API responses are serialized via explicit Pydantic response schemas that do not include internal configuration, credential status beyond a boolean `connected: true/false`, or any platform token.
- Adapter status endpoints expose only: `adapter_id`, `mock_enabled`, `read_enabled`, `write_enabled`, `last_successful_sync`, `last_failure` (timestamp only), `credential_status` (enum: `configured` / `missing` / `invalid` — no credential values).

---

## 2. External Writes Disabled by Default

### Feature-Flag Gating

Every external integration is gated by an environment variable that defaults to a safe value:

| Flag | Default | Effect when false/disabled |
|---|---|---|
| `EXTERNAL_WRITES_ENABLED` | `false` | Blocks all write operations to all adapters |
| `EXTERNAL_READS_ENABLED` | `false` | Blocks live read calls; Mock/ManualInbox used instead |
| `TIMOCOM_ENABLED` | `false` | TIMOCOM adapter falls back to Disabled implementation |
| `TRANSEU_ENABLED` | `false` | Trans.eu adapter falls back to Disabled implementation |
| `EMAIL_ENABLED` | `false` | Email adapter falls back to ManualInbox |
| `TRACKING_ENABLED` | `false` | Tracking provider falls back to disabled placeholder |
| `LOCAL_LLM_ENABLED` | `false` | LLM provider uses deterministic mock |
| `ANTHROPIC_LLM_ENABLED` | `false` | Anthropic placeholder inactive |
| `DEMO_MODE` | `true` | Enables safe demo fixtures; suppresses live calls |

The adapter layer enforces these flags at call time, not only at startup, so runtime flag changes (e.g., via env reload) take effect without code changes.

### Dry-Run Support

All write-capable adapters implement a `dry_run` parameter on every mutating method. When `dry_run=True`:

- The adapter constructs the full request payload and validates it.
- The request is logged as an audit event with `dry_run: true`.
- No network call is made; a synthetic successful response is returned.
- The ApprovalRequest workflow uses dry-run validation before presenting an action to a human reviewer.

---

## 3. The ApprovalRequest Gate

The ApprovalRequest is the single mandatory checkpoint before any consequential external action is executed.

### Scope

The following action categories ALWAYS require an ApprovalRequest:

- Accepting or rejecting a freight offer
- Publishing a freight offer to TIMOCOM or Trans.eu
- Sending a bid or price proposal
- Sending any outbound message or email on behalf of the company
- Confirming a rate with a carrier
- Issuing, modifying, or cancelling a transport order
- Approving or blacklisting a carrier or document
- Changing shipment dates
- Any invoicing or payment-adjacent action

### Lifecycle

1. The rule-based agent service constructs an `ApprovalRequest` record containing: action type, full payload, human-readable summary, risk classification, and the dry-run validation result.
2. The record is persisted to the database with status `pending`.
3. The UI presents the pending request to an authorized human reviewer with the full context.
4. The reviewer may Approve, Reject, or request Modification.
5. Only on explicit Approve does the system execute the action against the external adapter — with the exact payload that was reviewed (no re-generation).
6. The outcome (success, failure, adapter response) is appended to the ApprovalRequest record and an audit event is written.
7. Approved actions that fail at the adapter level do NOT auto-retry; a new ApprovalRequest cycle begins.

---

## 4. Audit Logging

- Every state-changing operation generates an immutable audit event stored in the `audit_log` table.
- Audit events include: `event_id`, `timestamp`, `actor` (user or system), `action_type`, `entity_type`, `entity_id`, `before_state` (JSON snapshot), `after_state` (JSON snapshot), `approval_request_id` (if applicable), `adapter_id` (if applicable), `dry_run` flag, `ip_address` (when available).
- Audit records are append-only in the application layer; no `UPDATE` or `DELETE` is issued against the audit table from application code.
- Log retention policy is configurable via `AUDIT_RETENTION_DAYS` (default: 365).

---

## 5. Untrusted-Content Handling & Prompt-Injection Defense

All content imported from external sources — freight-offer text, emails, PDFs, platform exchange data, carrier notes, document OCR output — is classified as **UNTRUSTED DATA**.

### Isolation boundary

- Untrusted content is stored in the database under typed columns with explicit maximum lengths.
- When passed to the LLM layer, untrusted content is always placed in a clearly delimited user-data section of the prompt, structurally separated from system instructions.
- The system prompt section explicitly instructs the LLM that the user-data section may contain adversarial text and must be treated as data to analyze, not as instructions to follow.
- The application never constructs prompts by naive string concatenation of user-supplied content with instruction text.

### Prompt-injection boundary

- The LLM is given a constrained output schema (Pydantic-validated JSON); free-form text generation is only permitted in designated summary fields with bounded length.
- LLM outputs are validated against the schema before use; fields that fail validation are discarded and flagged rather than passed downstream.
- LLM outputs never trigger ApprovalRequest creation or any write path directly; they inform the rule-based service which constructs actions independently.

### No browser automation

The system does not use Selenium, Playwright, Puppeteer, or any headless browser to interact with TIMOCOM, Trans.eu, or any other platform. CAPTCHA bypass is explicitly prohibited. Integration is exclusively through official API adapter interfaces (currently mock implementations).

---

## 6. File Upload Safety

### Size limits

- File upload endpoints enforce a configurable maximum file size (`MAX_UPLOAD_BYTES`, default: 10 MB).
- The limit is enforced before the file body is read into memory.
- The server returns HTTP 413 for over-limit files before processing begins.

### Type checks

- Accepted MIME types are restricted to a strict allowlist: `application/pdf`, `image/jpeg`, `image/png`, `image/tiff`, `image/webp`.
- MIME type is validated by inspecting file magic bytes (not the `Content-Type` header, which is user-controlled).
- Files failing type validation are rejected with HTTP 415 and not stored.

### Path traversal prevention

- Uploaded files are assigned a server-generated UUID filename with a fixed extension derived from the validated MIME type.
- The upload destination directory is resolved to an absolute path at startup; all file write operations use `os.path.join` with the resolved base path followed by an assertion that the final path starts with the base path.
- Original filenames provided by the client are stored in the database for display purposes only; they are never used in filesystem operations.

---

## 7. ORM & SQL Injection Prevention

- All database access uses SQLAlchemy 2.0 ORM or Core with bound parameters. Raw SQL strings are not used in application code.
- Search and filter parameters from HTTP requests are mapped to ORM filter expressions; they are never interpolated into SQL strings.
- Database migrations use Alembic with schema-level constraints (NOT NULL, CHECK, FK) to enforce data integrity at the storage layer.

---

## 8. Authorization Notes & Future Multi-User

### Current state (MVP / single-user)

- The MVP operates in a trusted single-user mode. All API endpoints are accessible from localhost without multi-user authentication.
- Session security relies on network isolation (localhost only) rather than per-user credentials.
- The `actor` field in audit events is recorded as the system or as a single configured user identity.

### Planned: multi-user

When the application is extended to multi-user operation, the following controls are planned:

- **Authentication**: session-based auth with CSRF protection, or token-based with short-lived JWTs and refresh-token rotation.
- **Role-based access control**: at minimum, roles `viewer`, `operator`, and `admin`. ApprovalRequest review requires `operator` or above.
- **IDOR prevention**: all database queries for user-visible resources will include an ownership or permission filter; numeric IDs in URLs will be validated against the authenticated user's accessible scope.
- **Per-user audit trail**: the `actor` field will carry the authenticated user's ID for all events.
- **Rate limiting**: per-user rate limits on all API endpoints, especially file upload and LLM-backed routes.

---

## 9. Dependency Security

- Python dependencies are pinned in `requirements.txt` / `pyproject.toml` with exact versions.
- Dependency vulnerability scanning (e.g., `pip-audit` or equivalent) is listed as a CI gate in the production readiness checklist.
- No dependency fetches occur at runtime; all packages are resolved at build time.
