# Threat Model

## Scope

This threat model covers Freight Copilot running as a local-first, single-operator deployment. It addresses threats relevant to the MVP state and flags mitigations that are planned for production/multi-user deployment.

**Asset inventory:**

- API credentials (TIMOCOM, Trans.eu, email, LLM providers)
- Operational freight data (offers, rates, margins, carrier contacts)
- Customer and carrier personal data (names, addresses, contacts — GDPR scope)
- Audit logs and decision history
- Imported documents (CMR, invoices, emails, offers as PDFs)

---

## Threat Table

### T-01: Credential Exposure via Repository

**Threat:** API keys, platform credentials, or database passwords are committed to version control or included in a build artifact.

**Impact:** Complete compromise of all connected platform accounts; potential unauthorized publishing of freight offers; financial loss.

**Mitigation:**
- `.env` file is gitignored; `.env.example` ships with placeholders only. *(Implemented)*
- Pre-commit hook or CI lint checks for secret patterns (e.g., `detect-secrets`). *(Planned)*
- Secrets manager (Vault, AWS Secrets Manager, or equivalent) for production deployments. *(Planned)*

---

### T-02: Credential Exposure via Log Files

**Threat:** Credentials or tokens leak into application logs or error traces.

**Impact:** Credential theft from log aggregation systems or shared log files.

**Mitigation:**
- Log sanitizer middleware strips known secret-pattern keys from all structured log output before writing. *(Implemented)*
- `Authorization` and `Cookie` headers are never logged. *(Implemented)*
- Log files are stored locally with filesystem permissions restricting read to the application user. *(Implemented)*
- Centralized log shipping uses redacted log streams only. *(Planned)*

---

### T-03: External API Misuse — Unauthorized Reads

**Threat:** The application performs unauthorized live reads from TIMOCOM or Trans.eu, violating contract terms or incurring unexpected usage costs.

**Impact:** Contract breach, API throttling, unexpected costs, data-use violations.

**Mitigation:**
- `EXTERNAL_READS_ENABLED=false` by default; all live API calls are blocked unless the flag is explicitly enabled. *(Implemented)*
- `TIMOCOM_ENABLED=false` and `TRANSEU_ENABLED=false` gates provide independent per-platform control. *(Implemented)*
- Adapter implementations are selected at startup; the Disabled implementation raises a non-network error on any call. *(Implemented)*
- Rate-limit handling is built into the Official adapter placeholder; exponential backoff and jitter prevent hammering. *(Planned — for Official implementation)*

---

### T-04: Unauthorized External Writes

**Threat:** The application publishes a freight offer, sends a bid, or confirms a rate without human review.

**Impact:** Financial commitment made without authorization; reputational damage; legal liability.

**Mitigation:**
- `EXTERNAL_WRITES_ENABLED=false` by default. *(Implemented)*
- Every write operation passes through the ApprovalRequest gate; no write path bypasses it. *(Implemented)*
- Dry-run validation executes before the ApprovalRequest is shown to the reviewer. *(Implemented)*
- The payload executed on approval is the exact reviewed payload; no re-generation occurs. *(Implemented)*
- Audit event is written for every approval decision and every adapter write attempt. *(Implemented)*

---

### T-05: Prompt Injection via Imported Content

**Threat:** Malicious text embedded in a freight offer, email body, PDF, or carrier note tricks the LLM into generating an instruction that causes an unauthorized action.

**Impact:** The LLM could be manipulated to produce a fabricated ApprovalRequest or suggest an action that bypasses human review.

**Mitigation:**
- All imported content is structurally separated from system instructions in every LLM prompt using explicit delimiters. *(Implemented)*
- System prompt explicitly instructs the model that the data section may contain adversarial content. *(Implemented)*
- LLM outputs are validated against a constrained Pydantic schema; free-form fields have bounded length. *(Implemented)*
- LLM outputs never directly create ApprovalRequests or trigger write paths; they inform the deterministic rule service only. *(Implemented)*
- Content is stored as typed, length-limited database fields before reaching the LLM layer. *(Implemented)*

---

### T-06: Malicious Imported Document (PDF / Image)

**Threat:** A maliciously crafted PDF or image exploits a vulnerability in the OCR or PDF-parsing library.

**Impact:** Remote code execution on the application host; data exfiltration.

**Mitigation:**
- File uploads are restricted to a strict MIME-type allowlist validated by magic bytes, not `Content-Type` header. *(Implemented)*
- File size is capped at `MAX_UPLOAD_BYTES` (default 10 MB) before the body is read. *(Implemented)*
- OCR/PDF processing runs on the validated file only; parser library versions are pinned and monitored. *(Implemented)*
- Future: process document parsing in a sandboxed subprocess or container. *(Planned)*

---

### T-07: Path Traversal via File Upload

**Threat:** An attacker uploads a file with a crafted filename (e.g., `../../etc/passwd`) to write or overwrite files outside the upload directory.

**Impact:** Arbitrary file write; potential code execution or configuration overwrite.

**Mitigation:**
- Server assigns a UUID-based filename; the client-provided filename is never used in filesystem operations. *(Implemented)*
- All file writes use an absolute base path resolved at startup; a path-prefix assertion is applied before every write. *(Implemented)*

---

### T-08: Oversized File Upload (DoS)

**Threat:** An attacker or misconfigured client sends an extremely large file, exhausting memory or disk space.

**Impact:** Application unavailability; disk exhaustion on the host.

**Mitigation:**
- `MAX_UPLOAD_BYTES` limit enforced before body is read into memory (streaming enforcement). *(Implemented)*
- HTTP 413 returned immediately for over-limit requests. *(Implemented)*
- Disk-space monitoring and alerting. *(Planned)*

---

### T-09: Model Hallucination Causing Incorrect Operational Data

**Threat:** The LLM generates a plausible but incorrect rate, distance, carrier name, or date that propagates into a decision without human verification.

**Impact:** Financial loss; incorrect freight commitment; damaged carrier relationship.

**Mitigation:**
- The LLM is used for suggestion and summarization only; it does not have a direct write path. *(Implemented)*
- All LLM-informed suggestions are presented to the human reviewer with the source data visible. *(Implemented)*
- Deterministic rule-based services handle all calculations involving rates, margins, and distances (using the Distance/Toll/Currency providers, not the LLM). *(Implemented)*
- LLM outputs are schema-validated; numeric fields are range-checked before display. *(Implemented)*

---

### T-10: Business Data Leakage to External LLM

**Threat:** Sensitive operational data (margin, customer names, carrier rates) is sent to a cloud LLM API and stored or used by the provider.

**Impact:** Competitive intelligence leakage; potential GDPR violation; breach of business confidentiality.

**Mitigation:**
- `ANTHROPIC_LLM_ENABLED=false` and `LOCAL_LLM_ENABLED=false` by default; cloud LLM calls are opt-in. *(Implemented)*
- `DEMO_MODE=true` default uses only fixture data with no real operational content. *(Implemented)*
- Data minimization: only the fields necessary for the specific LLM task are included in the prompt; full records are not serialized wholesale. *(Implemented)*
- Employer must explicitly authorize which data may be sent to external AI services (see `EMPLOYER_DISCOVERY_QUESTIONS.md`). *(Requires employer decision)*
- Local LLM option available as a privacy-preserving alternative for sensitive tasks. *(Planned)*

---

### T-11: Customer and Carrier Personal Data Exposure (GDPR)

**Threat:** Personal data (names, phone numbers, email addresses, company registration numbers) of customers and carriers is exposed in logs, API responses, or to unauthorized users.

**Impact:** GDPR Article 5 violation; regulatory fines; reputational damage.

**Mitigation:**
- Personal data fields are not included in log output by default; log sanitizer covers common PII field names. *(Implemented)*
- API response schemas use explicit field allowlists; personal data fields are excluded from list/search endpoints where not needed. *(Implemented)*
- Database access is parameterized; no raw PII is interpolated into queries. *(Implemented)*
- Data retention and deletion workflows. *(Planned)*
- GDPR data-subject access and erasure request handling. *(Planned)*
- Data Processing Agreement with any cloud service provider that receives personal data. *(Planned — requires legal review)*

---

### T-12: Unsafe Audit Logs

**Threat:** Audit log records are modified or deleted, hiding unauthorized actions or covering tracks.

**Impact:** Loss of accountability; inability to investigate incidents; regulatory non-compliance.

**Mitigation:**
- Application code issues no `UPDATE` or `DELETE` against the `audit_log` table. *(Implemented)*
- Database user for the application has `INSERT` and `SELECT` only on the audit table (when Postgres is used with a restricted role). *(Planned for Postgres deployment)*
- Audit log export and off-host archival. *(Planned)*
- Log integrity checksums or append-only log storage. *(Planned)*

---

### T-13: Accidental Production Actions in Development/Demo

**Threat:** A developer or demo user accidentally triggers a real external write because the environment is misconfigured with production credentials.

**Impact:** Unauthorized freight publication; real financial commitment; platform account issues.

**Mitigation:**
- `DEMO_MODE=true` and all external flags default to `false`; production requires explicit opt-in. *(Implemented)*
- `EXTERNAL_WRITES_ENABLED` must be explicitly set to `true`; it is not inherited from any other flag. *(Implemented)*
- UI surfaces a visible banner when `DEMO_MODE=false` and any external adapter is enabled. *(Implemented)*
- Separate `.env` files for dev, staging, and production with enforced naming conventions. *(Planned)*

---

### T-14: Insufficient Audit Trail

**Threat:** A consequential action is taken with no audit record, or the audit record lacks sufficient detail to reconstruct what happened.

**Impact:** Inability to investigate disputes; regulatory non-compliance; operational disputes with carriers or customers.

**Mitigation:**
- Audit events are mandatory for all ApprovalRequest lifecycle transitions and all adapter write attempts. *(Implemented)*
- Audit records include before/after state snapshots, actor, timestamp, action type, and entity identity. *(Implemented)*
- Failed write attempts are also audited with the error detail. *(Implemented)*
- Audit log coverage is part of the production readiness checklist. *(Planned)*

---

### T-15: Cross-Site Scripting (XSS)

**Threat:** Malicious scripts embedded in imported freight text, carrier names, or email content are rendered as HTML in the Jinja2 UI.

**Impact:** Session hijacking; UI manipulation; data exfiltration via browser.

**Mitigation:**
- Jinja2 auto-escaping is enabled globally; all variable interpolations in templates are HTML-escaped by default. *(Implemented)*
- Content Security Policy (CSP) header set to restrict inline scripts and external script sources. *(Planned)*
- Explicit `| e` escaping used as a secondary defense for any template variables derived from untrusted content. *(Implemented)*

---

### T-16: SQL Injection

**Threat:** Unsanitized user input is interpolated into a SQL query, allowing database manipulation.

**Impact:** Data exfiltration; data destruction; authentication bypass.

**Mitigation:**
- All queries use SQLAlchemy ORM or Core with bound parameters; no raw SQL string interpolation in application code. *(Implemented)*
- Code review policy prohibits `text()` with f-string interpolation. *(Implemented)*

---

### T-17: Insecure Direct Object Reference (IDOR)

**Threat:** A user accesses a freight record, carrier record, or document belonging to another user by guessing or modifying a numeric ID in a URL.

**Impact:** Unauthorized data access; data leakage across operator accounts.

**Mitigation:**
- In single-user MVP, all data belongs to the single operator; IDOR is not a cross-user threat. *(Acknowledged for MVP)*
- For future multi-user: all ORM queries for user-visible resources will include an ownership or permission filter scoped to the authenticated user. *(Planned)*
- UUIDs rather than sequential integers as public-facing entity identifiers to reduce enumeration risk. *(Planned)*

---

### T-18: Weak Authorization (Future Multi-User)

**Threat:** A lower-privileged user performs an ApprovalRequest review, approves a rate, or accesses another user's operational data.

**Impact:** Unauthorized commitments; data leakage; fraud.

**Mitigation:**
- Single-user MVP: not applicable. *(Acknowledged)*
- Multi-user: role-based access control with `viewer`, `operator`, `admin` roles; ApprovalRequest review requires `operator` or above. *(Planned)*
- Authorization checks enforced in the service layer, not only in route handlers. *(Planned)*

---

### T-19: Dependency Vulnerabilities

**Threat:** A known vulnerability in a pinned Python dependency (FastAPI, SQLAlchemy, Jinja2, PDF/OCR parser, etc.) is exploited.

**Impact:** Varies by vulnerability — RCE, data leakage, DoS.

**Mitigation:**
- All dependencies are pinned to exact versions. *(Implemented)*
- `pip-audit` or equivalent runs as a CI gate. *(Planned)*
- Dependabot or Renovate for automated vulnerability PRs. *(Planned)*

---

### T-20: No Scraping / Browser Automation

**Threat:** Browser automation against TIMOCOM or Trans.eu violates platform terms of service, triggers account suspension, or introduces CAPTCHA-bypass tooling that creates additional attack surface.

**Impact:** Platform account suspension; legal liability; loss of access.

**Mitigation:**
- Browser automation (Selenium, Playwright, Puppeteer, etc.) is explicitly prohibited in the codebase and architecture. *(Implemented — by design)*
- Integration is exclusively via official API adapter interfaces or manual import. *(Implemented)*
- The Mock and ManualInbox implementations provide full functionality without any platform contact. *(Implemented)*
