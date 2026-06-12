# Trans.eu Integration Checklist

## Purpose

This checklist defines every step and decision required before the Trans.eu Official adapter can replace the current placeholder. It follows the same structure as `TIMOCOM_INTEGRATION_CHECKLIST.md`.

The current state: the `TransEuOfficialAdapter` class exists as a placeholder that raises `NotImplementedError` on all methods. The Mock and Disabled implementations are fully functional. No live Trans.eu API calls are made.

Trans.eu publishes public API documentation; the general capabilities described below are based on publicly available information. The specific API scopes available to the company depend on their Trans.eu contract.

---

## Section 1: Missing Information — Needed from Employer

### 1.1 Contract and API Scope Access

- [ ] Does the company have an active Trans.eu API access agreement (separate from the web platform subscription)?
- [ ] Which API scopes are enabled under the company's agreement? Candidates described in Trans.eu public documentation include:
  - Creating freight (load) offers
  - Publishing / unpublishing freight offers to the exchange
  - Updating offer details
  - Cancelling offer publication
  - Archiving offers
  - Reading offer statuses and history
  - Accessing received proposals (carrier bids)
  - Price negotiation (counter-offer flow)
  - Accepted-freight details (transport order data after acceptance)
  - Monitoring tasks (watching specific offers or routes for activity)
- [ ] Are there any API scopes the company explicitly does NOT have access to?
- [ ] Are there contractual restrictions on automated API usage (rate limits, permitted automation, data handling)?

### 1.2 Credentials and Sandbox

- [ ] What authentication method does the Trans.eu API use under this contract (OAuth 2.0 with client credentials, authorization code flow, API key, or other)?
- [ ] Are there separate credentials for the sandbox / staging environment?
- [ ] If yes, who holds the sandbox credentials?
- [ ] If no sandbox: what is the accepted approach for testing write operations before going live?
- [ ] Who is the Trans.eu technical contact or account manager for API questions?

### 1.3 Permitted Use Cases

- [ ] Is automated freight publication permitted under the contract?
- [ ] Is automated proposal/bid reading permitted?
- [ ] Are there call frequency or daily volume limits?
- [ ] What happens if an API limit is exceeded — temporary throttle, or account action?

---

## Section 2: Capabilities to Confirm

For each capability, confirm whether the company's contract scope enables it. Mark as **Confirmed**, **Not available**, or **Unknown**.

| Capability | API scope required | Status |
|---|---|---|
| Create freight offer (draft) | Freight creation scope | Unknown |
| Publish offer to exchange | Offer publication scope | Unknown |
| Update offer details | Offer update scope | Unknown |
| Cancel publication | Cancellation scope | Unknown |
| Archive offer | Archive scope | Unknown |
| Read offer status / history | Status read scope | Unknown |
| Read received proposals (bids) | Proposals scope | Unknown |
| Price negotiation (counter-offer) | Negotiation scope | Unknown |
| Accepted-freight details | Accepted freight scope | Unknown |
| Monitoring tasks (route / offer watch) | Monitoring scope | Unknown |
| Carrier/company identity data | Company info scope | Unknown |

Capabilities not confirmed as available must not be implemented; the corresponding adapter methods should raise `CapabilityNotAvailableError`.

---

## Section 3: Credential Handling

- [ ] Add Trans.eu credentials to `.env` under the variable names:
  - `TRANSEU_CLIENT_ID`
  - `TRANSEU_CLIENT_SECRET`
  - `TRANSEU_BASE_URL` (sandbox vs production)
  - `TRANSEU_TOKEN_URL` (OAuth token endpoint)
- [ ] Update `.env.example` with placeholder values and comments.
- [ ] Confirm credentials are stored only in `.env`; never in code, config files, or database.
- [ ] Confirm the log sanitizer covers the new variable names.
- [ ] Implement OAuth 2.0 token acquisition and refresh; store access tokens in memory only.
- [ ] Test that expired or invalid credentials return `credential_status: invalid` in the adapter status response.
- [ ] Confirm the token expiry and refresh cadence from Trans.eu documentation; configure the refresh margin accordingly.

---

## Section 4: Rate Limits and Error Handling

- [ ] Obtain rate limits from Trans.eu documentation or account manager:
  - Requests per second
  - Requests per minute / hour / day
  - Separate limits for read vs write endpoints
- [ ] Implement a client-side rate-limit tracker.
- [ ] Map Trans.eu HTTP error codes and API error objects to the application's typed error hierarchy:
  - `401` → `CredentialError`
  - `403` → `PermissionError` (scope not available)
  - `429` → `RateLimitError` with `retry_after`
  - `409` (conflict / duplicate) → `IdempotencyConflictError`
  - `422` (validation error) → `AdapterRequestError` with field-level detail
  - `5xx` → `AdapterTemporaryError`
- [ ] Confirm how Trans.eu API expresses idempotency: does it use a client-provided key in a header, or is deduplication handled by the platform?

---

## Section 5: Domain Model Mapping

### Inbound: reading offers and proposals

- [ ] Map Trans.eu freight offer response to `FreightOfferImport` schema:
  - Loading location (address, country code, geocoordinates)
  - Unloading location (address, country code, geocoordinates)
  - Loading date and time window
  - Unloading date and time window
  - Cargo description
  - Weight (kg), volume (m³), loading meters (LDM)
  - Vehicle type / body type requirements
  - ADR / special requirements flags
  - Price (if present) and currency
  - Offer ID, publication timestamp, expiry
  - Offeror company Trans.eu ID and name
- [ ] Map Trans.eu proposal (carrier bid) fields to `CarrierProposal` domain schema.

### Outbound: publishing freight

- [ ] Map `FreightOfferPublish` domain schema to Trans.eu freight creation request:
  - Loading and unloading location format (Trans.eu may require ISO country codes + city or geocoordinates)
  - Date/time format (ISO 8601; confirm timezone handling — application uses Europe/Warsaw)
  - Cargo type code mapping (Trans.eu likely uses enumerated cargo categories)
  - Vehicle type code mapping
  - Price and currency fields (EUR and PLN)
  - Contact information fields (which company contact details to publish)
- [ ] Identify mandatory Trans.eu fields not covered by the domain model; raise `MappingError` if required fields are absent.

### Negotiation flow

- [ ] Map `PriceProposal` domain schema to Trans.eu negotiation request.
- [ ] Map Trans.eu negotiation state transitions (pending, countered, accepted, rejected) to the `NegotiationStatus` domain enum.

### Accepted-freight and transport orders

- [ ] Map Trans.eu accepted-freight detail response to `TransportOrder` domain schema.
- [ ] Identify fields in Trans.eu accepted-freight that are not in the current domain model; decide whether to add them.

---

## Section 6: Dry-Run Rollout Steps

Complete these steps in order.

- [ ] **Step 1 — Read-only, sandbox**: Set `TRANSEU_ENABLED=true`, `EXTERNAL_READS_ENABLED=true`, `TRANSEU_BASE_URL=<sandbox_url>`. Read available offers. Confirm domain-model parsing. Review audit log.
- [ ] **Step 2 — Read-only, production**: Switch to production URL. Read a sample of live offers. Compare against what the operator sees in the Trans.eu web interface. Confirm no unexpected account activity.
- [ ] **Step 3 — Write dry-run, sandbox**: Keep `EXTERNAL_WRITES_ENABLED=false`. Call `publish_freight` with `dry_run=True` on sandbox. Inspect audit log payloads with the operator. Confirm field mapping is correct.
- [ ] **Step 4 — Write live, sandbox**: Set `EXTERNAL_WRITES_ENABLED=true`, sandbox URL. Publish one test offer via full ApprovalRequest workflow. Confirm the offer appears in the Trans.eu sandbox interface. Confirm audit trail.
- [ ] **Step 5 — Write live, production, supervised**: Switch to production URL. Execute one real publication with the operator monitoring the Trans.eu web UI. Confirm. Monitor for 48 hours.
- [ ] **Step 6 — Negotiation flow**: Enable proposal reading and negotiation after basic publication is stable. Test the counter-offer flow end-to-end with a real carrier in sandbox if possible.
- [ ] **Step 7 — Full rollout**: Remove dry-run restrictions. Document rate-limit headroom. Update operational runbook.

---

## Section 7: Testing Requirements

Before the Official adapter is merged to main:

- [ ] Unit tests for all domain-model mapping functions (Trans.eu response → domain, domain → Trans.eu request)
- [ ] Unit tests for OAuth token acquisition and refresh logic
- [ ] Adapter integration tests against sandbox (skipped in CI if sandbox credentials absent)
- [ ] End-to-end test: offer creation → publication → ApprovalRequest → approval → adapter write → status read → audit log
- [ ] Negotiation flow test: proposal received → counter-offer → acceptance
- [ ] Negative tests: expired token, missing scope, rate limit, malformed response, missing required mapping fields
- [ ] Confirm Mock implementation passes the same interface contract tests as the Official implementation

---

## Current Blockers (as of documentation date)

All items in Section 1 are unresolved. No implementation work should begin until the employer provides contract and access information. The Mock and ManualImport paths provide full operational capability in the meantime.
