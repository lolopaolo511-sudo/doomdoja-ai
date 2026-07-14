# Production Readiness Checklist

## Purpose

This checklist tracks the path from the local MVP state to a production-ready deployment. Items are grouped into work streams. MVP state is noted where the current implementation already satisfies the requirement at the single-user local level.

Use this checklist when preparing a deployment for real operational use with live platform connections and real freight data.

---

## 1. Authentication and Multi-User

- [ ] **Implement session-based or token-based authentication.** MVP runs on localhost without auth (trusted single-user). Production requires login. *(MVP state: no auth — localhost only)*
- [ ] **Define roles**: `viewer` (read-only), `operator` (full operational access, can create and review ApprovalRequests), `admin` (user management, system config). *(Planned)*
- [ ] **Enforce role checks in the service layer**, not only in route handlers; authorization must be independent of presentation logic. *(Planned)*
- [ ] **Implement CSRF protection** for session-based auth. *(Planned)*
- [ ] **Configure secure session cookies**: `HttpOnly`, `Secure`, `SameSite=Strict`, short lifetime with sliding renewal. *(Planned)*
- [ ] **Implement password policy** (minimum length, bcrypt hashing, no plaintext storage). *(Planned)*
- [ ] **Add IDOR protection**: all ORM queries scoped to the authenticated user's accessible data scope. *(Planned)*
- [ ] **Add per-user rate limiting** on all API endpoints. *(Planned)*
- [ ] **Update audit log** `actor` field to carry authenticated user ID for all events. *(Planned)*
- [ ] **Document user provisioning process**: how are new operator accounts created and revoked? *(Planned)*

---

## 2. Database: PostgreSQL and Migrations

- [ ] **Switch from SQLite to PostgreSQL** by setting `DATABASE_URL` to a Postgres connection string. The ORM supports both; no code change required. *(MVP state: SQLite default)*
- [ ] **Create a dedicated application database user** with minimum required permissions:
  - `SELECT`, `INSERT`, `UPDATE`, `DELETE` on application tables
  - `INSERT`, `SELECT` only on `audit_log` table
  - No `DROP`, `TRUNCATE`, or DDL permissions in production
- [ ] **Run all Alembic migrations** against the production database before first use. *(MVP state: migrations exist and apply cleanly)*
- [ ] **Confirm migration history is clean**: `alembic current` shows the latest revision with no pending migrations.
- [ ] **Test rollback path**: confirm at least the most recent migration can be rolled back without data loss.
- [ ] **Enable connection pooling** (SQLAlchemy `pool_size`, `max_overflow`) appropriate for expected concurrency.
- [ ] **Set Postgres connection timeout and statement timeout** to prevent runaway queries.
- [ ] **Enable pg_stat_statements** or equivalent for query performance monitoring.

---

## 3. Secrets Management

- [ ] **Move secrets from .env to a secrets manager** (HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, or equivalent) for deployments beyond a single developer workstation. *(MVP state: .env file, gitignored)*
- [ ] **Rotate all credentials** before first production use.
- [ ] **Verify .gitignore** prevents .env from being committed; add CI check.
- [ ] **Run secret-scanning tool** (e.g., `detect-secrets`, `truffleHog`) on repository history before going live.
- [ ] **Confirm log sanitizer covers all new credential variable names** added during integration setup.
- [ ] **Document credential rotation procedure** for each adapter (TIMOCOM, Trans.eu, email, LLM providers).

---

## 4. Enabling Real Adapters Safely

For each adapter, follow the per-adapter dry-run rollout steps documented in the integration checklists before setting any write flag to `true` in production.

### 4.1 TIMOCOM

- [ ] Answer all questions in `TIMOCOM_INTEGRATION_CHECKLIST.md` Section 1.
- [ ] Complete Sections 3–6 of the checklist.
- [ ] Pass all testing requirements in Section 7.

### 4.2 Trans.eu

- [ ] Answer all questions in `TRANSEU_INTEGRATION_CHECKLIST.md` Section 1.
- [ ] Complete Sections 3–6 of the checklist.
- [ ] Pass all testing requirements in Section 7.

### 4.3 Email

- [ ] Confirm email provider and API access method (Microsoft Graph, Gmail API, IMAP).
- [ ] Configure OAuth credentials and add to secrets store.
- [ ] Set `EMAIL_ENABLED=true` and test with a test mailbox before pointing at the operational inbox.
- [ ] Confirm outbound email is gated by the ApprovalRequest workflow.

### 4.4 LLM

- [ ] Answer Group 3 questions in `EMPLOYER_DISCOVERY_QUESTIONS.md` before enabling any cloud LLM.
- [ ] If cloud LLM is approved: configure credentials, set appropriate flag, test with non-sensitive fixture data first.
- [ ] If only local LLM is approved: set up local endpoint, configure `LOCAL_LLM_ENABLED=true`, test LLM provider contract.

---

## 5. Monitoring and Alerting

- [ ] **Application health endpoint** (`/health`) returns HTTP 200 with database connectivity and adapter status. *(MVP state: endpoint exists)*
- [ ] **Structured logging to file or log aggregator** (JSON format, log level configurable via env). *(MVP state: structured logging implemented, output to stdout)*
- [ ] **Error rate alerting**: alert on any unhandled exception or HTTP 5xx rate above threshold.
- [ ] **Adapter failure alerting**: alert when any enabled adapter records consecutive failures or `last_failure` is recent.
- [ ] **ApprovalRequest queue depth alerting**: alert when pending ApprovalRequests are older than a configurable threshold (e.g., 4 hours without review).
- [ ] **Disk space monitoring**: alert at 80% disk usage on the data volume.
- [ ] **Database connection pool monitoring**: alert on pool exhaustion.
- [ ] **Rate limit headroom monitoring**: alert when API call volume approaches configured rate limits for any adapter.
- [ ] **Uptime monitoring**: external check confirms the application responds every N minutes.

---

## 6. Backups

- [ ] **Database backup schedule**: daily full backup, transaction log backup (Postgres WAL archiving or equivalent). *(MVP state: SQLite file — manual copy only)*
- [ ] **Backup storage location**: off-host (different physical location or cloud storage bucket).
- [ ] **Backup encryption**: backups encrypted at rest.
- [ ] **Backup retention**: minimum 30 days of daily backups; 12 months of monthly backups (or as required by GDPR / employer policy).
- [ ] **Backup restoration test**: perform a test restore quarterly; document the procedure.
- [ ] **Uploaded document backup**: the file upload directory is included in the backup scope.
- [ ] **Recovery Time Objective (RTO) and Recovery Point Objective (RPO)** defined and tested.

---

## 7. Audit Log Retention

- [ ] **Audit log retention policy** configured via `AUDIT_RETENTION_DAYS` (default 365; verify against GDPR and employer requirements). *(MVP state: configurable, default 365 days)*
- [ ] **Audit log export**: implement a scheduled export of audit records older than N days to cold storage (JSON or CSV).
- [ ] **Audit log off-host copy**: audit records are included in the backup scope.
- [ ] **Audit log access control**: only `admin` role can query the full audit log; operators can see their own records.
- [ ] **Verify no UPDATE or DELETE on audit_log** from application code; add integration test that asserts this.

---

## 8. GDPR and Data Residency

- [ ] **Confirm data residency requirements** (Group 4 of `EMPLOYER_DISCOVERY_QUESTIONS.md`) with the employer's DPO.
- [ ] **Ensure database server and backup storage reside in the approved geography** (typically EU).
- [ ] **Implement data retention automation**: personal data older than the agreed retention period is deleted or anonymized automatically.
- [ ] **Implement data subject rights workflows**: ability to export and delete a specific person's data on request.
- [ ] **Document data flows**: which personal data is sent to which external system (TIMOCOM, Trans.eu, email provider, LLM API).
- [ ] **Review data processing agreements (DPA)** with all external service providers that receive personal data.
- [ ] **Confirm carrier and customer contact data fields** are not logged in full in audit events (log IDs, not PII).

---

## 9. Load and Performance

- [ ] **Baseline performance test**: measure response times for the 10 most-used endpoints under expected single-user load.
- [ ] **Database index review**: confirm indexes exist on all foreign keys, filter columns, and sort columns used in list endpoints.
- [ ] **Large dataset test**: import 1,000+ freight records and confirm UI and API response times remain acceptable.
- [ ] **File upload stress test**: confirm oversized file rejection works correctly before the file is read into memory.
- [ ] **LLM latency**: if cloud LLM is enabled, measure end-to-end latency for the slowest LLM-backed operation; confirm the UI handles slow responses gracefully (loading state, timeout).
- [ ] **Adapter timeout configuration**: all external API calls have a configured timeout; the application does not hang indefinitely on an unresponsive API.

---

## 10. Test Coverage Gates

- [ ] **Unit test coverage** for all service-layer business logic: rate calculation, margin calculation, ApprovalRequest lifecycle, domain model mapping.  *(MVP state: core tests exist)*
- [ ] **Integration tests** for all adapter interface contracts (Mock implementation must pass the same tests as Official).
- [ ] **End-to-end test** for the ApprovalRequest workflow: create → review → approve → adapter call → audit log.
- [ ] **Security test**: path traversal attempt on file upload returns 400 (not 500 and not a written file).
- [ ] **Prompt injection test**: a payload containing instruction-like text in the untrusted content section does not alter the LLM task or produce an unexpected action.
- [ ] **Test coverage threshold**: CI fails if coverage on the `services/` and `adapters/` packages drops below 80%.
- [ ] **All tests pass on clean checkout** with only `.env.example` values (no real credentials required for test suite).

---

## 11. CI/CD

- [ ] **CI pipeline** runs on every pull request: lint, type-check, test suite, dependency vulnerability scan. *(MVP state: not yet configured)*
- [ ] **Linting**: `ruff` or equivalent, `mypy` type checking.
- [ ] **Dependency vulnerability scan**: `pip-audit` or equivalent.
- [ ] **Secret scanning**: `detect-secrets` pre-commit hook and CI scan.
- [ ] **Migration check**: CI confirms no unmigrated model changes (Alembic autogenerate produces no diff).
- [ ] **Automated deployment to staging** on merge to main.
- [ ] **Manual promotion to production** with a deployment checklist step.
- [ ] **Rollback procedure** documented: how to roll back a failed deployment (code and database migration).

---

## 12. Incident Runbook

- [ ] **Runbook document exists** covering at minimum:
  - How to check application health and current adapter status
  - How to disable a specific adapter immediately (env flag + restart)
  - How to pause all external writes immediately
  - How to investigate a pending ApprovalRequest that should not have been created
  - How to manually reject a pending ApprovalRequest
  - How to restore from backup
  - Who to contact at TIMOCOM and Trans.eu for API incidents
  - GDPR breach notification procedure and timeline (72-hour reporting obligation)
- [ ] **On-call contact list** defined: who responds to application alerts outside business hours.
- [ ] **Post-incident review template** available.

---

## Summary Table

| Work stream | MVP state | Production gate |
|---|---|---|
| Authentication | No auth (localhost) | Required before multi-user or remote access |
| Database | SQLite | PostgreSQL required for production |
| Secrets management | .env file | Secrets manager recommended |
| TIMOCOM adapter | Mock/Disabled | Checklist complete + dry-run passed |
| Trans.eu adapter | Mock/Disabled | Checklist complete + dry-run passed |
| Email adapter | ManualInbox | Employer approval + credential setup |
| LLM providers | Deterministic mock | Employer data-policy approval |
| Monitoring | Health endpoint | Full alerting stack before go-live |
| Backups | None | Daily backup + tested restore |
| Audit retention | 365-day default | Employer/GDPR policy confirmation |
| GDPR controls | Basic field exclusion | DPO review + retention automation |
| CI/CD | None | Required before team use |
| Test coverage | Core tests exist | 80% gate on services + adapters |
