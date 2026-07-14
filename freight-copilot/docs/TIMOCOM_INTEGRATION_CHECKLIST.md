# TIMOCOM Integration Checklist

## Purpose

This checklist defines every step and decision required before the TIMOCOM Official adapter can replace the current placeholder. It is organized as a sequence of gates: work in a later section only begins once the earlier sections are resolved.

The current state: the `TiMOCOMOfficialAdapter` class exists as a placeholder that raises `NotImplementedError` on all methods. The Mock and Disabled implementations are fully functional. No live TIMOCOM API calls are made.

---

## Section 1: Missing Information — Needed from Employer

The following must be answered by the employer before any implementation work begins. These are contract and access questions, not technical questions.

### 1.1 Contract and API Module Access

- [ ] Does the company have an active TIMOCOM API contract (separate from UI/web access)?
- [ ] Which API modules are included in the contract? Candidates described publicly by TIMOCOM include:
  - Freight exchange search (inbound offers)
  - Freight offer/load insertion (publishing our own loads)
  - Transport order management
  - Shipment tracking / telematic data exchange
  - Price overviews / rate benchmarking
  - Carrier/company verification and rating data
- [ ] Is the current contract scope sufficient for the planned use cases, or does it need to be upgraded?
- [ ] Are there any contractual restrictions on automated API access (rate limits, permitted use cases, data retention obligations)?
- [ ] What is the contract renewal / notice period, so integration work is not blocked by expiry?

### 1.2 Credentials and Sandbox

- [ ] What authentication method does the company's TIMOCOM API contract use (API key, OAuth 2.0, client certificate, or other)?
- [ ] Does TIMOCOM provide a sandbox / test environment under this contract?
- [ ] If yes, are sandbox credentials available? Who holds them?
- [ ] If no sandbox, how should API integration be tested before going live?
- [ ] Who is the TIMOCOM account manager or technical contact for API questions?

### 1.3 Permitted Use Cases

- [ ] Is automated freight search (reading offers) permitted under the contract?
- [ ] Is automated offer insertion (publishing loads) permitted under the contract?
- [ ] Are there restrictions on the frequency or volume of API calls?
- [ ] Can the company's TIMOCOM account be suspended for excessive or malformed API calls?

---

## Section 2: Capabilities to Confirm

For each capability below, confirm whether the company's contract scope enables it before implementing the corresponding adapter method. Mark each as **Confirmed**, **Not available**, or **Unknown**.

| Capability | Contract scope required | Status |
|---|---|---|
| Freight search (inbound loads to carry) | Freight exchange search module | Unknown |
| Own-load publication (publishing our freight) | Freight insertion module | Unknown |
| Transport order creation / management | Transport order module | Unknown |
| Shipment tracking (outbound) | Tracking / telematic module | Unknown |
| Price overview / market rate benchmarks | Price overview module | Unknown |
| Carrier/company identity verification | Company verification module | Unknown |
| Carrier rating / feedback access | Rating module | Unknown |

Capabilities not confirmed as available must not be implemented; the corresponding adapter methods should raise `CapabilityNotAvailableError` rather than `NotImplementedError`.

---

## Section 3: Credential Handling

- [ ] Add TIMOCOM credentials to `.env` under the variable names:
  - `TIMOCOM_CLIENT_ID` (if OAuth)
  - `TIMOCOM_CLIENT_SECRET` (if OAuth)
  - `TIMOCOM_API_KEY` (if key-based)
  - `TIMOCOM_BASE_URL` (for sandbox vs production switching)
- [ ] Update `.env.example` with placeholder values and comments.
- [ ] Confirm that credentials are stored only in `.env`; never in code, config files, or database.
- [ ] Confirm the log sanitizer covers the new variable names.
- [ ] If OAuth: implement token refresh logic; store access tokens in memory only (never on disk or in the database).
- [ ] Test that a missing or invalid credential causes `credential_status: invalid` in the adapter status response, not an unhandled exception.

---

## Section 4: Rate Limits and Error Handling

- [ ] Obtain the API rate limits from TIMOCOM documentation or account manager:
  - Requests per second
  - Requests per day / month
  - Burst limit
- [ ] Implement a rate-limit tracker in the adapter that enforces these limits client-side before sending requests.
- [ ] Map TIMOCOM HTTP error codes to the application's typed error hierarchy:
  - `401` / `403` → `CredentialError`
  - `429` → `RateLimitError` with `retry_after` from response headers
  - `5xx` → `AdapterTemporaryError`
  - `4xx` (validation) → `AdapterRequestError` with detail
- [ ] Test that a `RateLimitError` surfaces to the operator UI as a clear non-alarming message, not a stack trace.

---

## Section 5: Domain Model Mapping

The following mapping work is required before the adapter can return data that the application domain services can consume:

### Freight offer (inbound, search results)

- [ ] Map TIMOCOM freight offer fields to `FreightOfferImport` schema:
  - Loading location (address, geocoordinates)
  - Unloading location (address, geocoordinates)
  - Loading date range
  - Unloading date range
  - Cargo type / description
  - Weight, volume, loading meters
  - Vehicle type required
  - Offered price (if present) and currency
  - Offer ID and publication timestamp
  - Offeror company ID and name
- [ ] Identify fields TIMOCOM provides that have no current domain equivalent; decide: add field or discard.
- [ ] Identify domain fields that TIMOCOM does not provide; mark as `None` / missing in the import schema.

### Own-load publication (write path)

- [ ] Map `FreightOfferPublish` domain schema to TIMOCOM insertion request fields.
- [ ] Identify mandatory TIMOCOM fields not covered by the domain model; raise `MappingError` if required fields are absent.
- [ ] Confirm how TIMOCOM represents partial-load (LTL) vs full-truck-load (FTL) in the API.

### Transport order (if available)

- [ ] Map `TransportOrder` domain schema to TIMOCOM transport order fields.

---

## Section 6: Dry-Run Rollout Steps

Complete these steps in order. Do not advance to the next step until the current one passes.

- [ ] **Step 1 — Read-only, sandbox**: Set `TIMOCOM_ENABLED=true`, `EXTERNAL_READS_ENABLED=true`, `TIMOCOM_BASE_URL=<sandbox_url>`. Run freight searches. Confirm results parse correctly into the domain model. Review adapter status and audit log.
- [ ] **Step 2 — Read-only, production**: Switch `TIMOCOM_BASE_URL=<production_url>`. Run a small number of searches. Compare results against what the operator sees in the TIMOCOM web UI. Confirm no unexpected account activity.
- [ ] **Step 3 — Write dry-run, sandbox**: Set `EXTERNAL_WRITES_ENABLED=false` (still). Call publication methods with `dry_run=True` on sandbox. Confirm audit log entries contain correctly formed payloads. Review payloads with the operator.
- [ ] **Step 4 — Write live, sandbox**: Set `EXTERNAL_WRITES_ENABLED=true`, `TIMOCOM_BASE_URL=<sandbox_url>`. Publish one test offer via ApprovalRequest workflow. Confirm offer appears in TIMOCOM sandbox. Confirm audit log records the full lifecycle.
- [ ] **Step 5 — Write live, production, supervised**: Switch to production URL. Execute one real publication with the operator watching the TIMOCOM web UI. Confirm. Monitor for 48 hours.
- [ ] **Step 6 — Full rollout**: Remove dry-run restrictions. Confirm rate-limit headroom. Document operational runbook.

---

## Section 7: Testing Requirements

Before the Official adapter is merged to main:

- [ ] Unit tests for all domain-model mapping functions (TIMOCOM response → domain, domain → TIMOCOM request)
- [ ] Adapter-level integration tests running against the sandbox (skipped in CI if sandbox credentials not present)
- [ ] End-to-end test: freight search → ApprovalRequest creation → human approval → adapter write → audit log verification
- [ ] Negative tests: invalid credentials, rate limit response, malformed API response, missing required fields
- [ ] Confirm Mock implementation still passes the same interface contract tests as the Official implementation

---

## Current Blockers (as of documentation date)

All items in Section 1 are unresolved. No implementation work should begin until the employer answers the contract and access questions. The Mock and ManualImport paths provide full operational capability in the meantime.
