# Integration Architecture

## Overview

Freight Copilot uses a layered adapter architecture that completely separates the application domain from external platform details. Every integration — whether a freight exchange, email service, distance calculator, or LLM — implements a common interface contract. The application core only ever calls the interface; the concrete implementation is selected at startup based on feature flags and credential availability.

This design means the application runs fully and correctly with no external network access, using mock or manual-import implementations that are behaviorally identical to the real ones from the application's point of view.

---

## The Common Adapter Contract

All adapters expose the following fields as part of their runtime metadata:

| Field | Type | Description |
|---|---|---|
| `adapter_id` | `str` | Stable identifier for the adapter (e.g., `timocom`, `transeu`, `email`) |
| `capabilities` | `list[str]` | What this adapter can do (e.g., `["freight_search", "offer_insert"]`) |
| `configured_status` | `str` | `configured` / `unconfigured` / `invalid_credentials` |
| `read_enabled` | `bool` | Whether live read calls are permitted at this moment |
| `write_enabled` | `bool` | Whether live write calls are permitted at this moment |
| `mock_enabled` | `bool` | Whether this adapter is running in mock mode |
| `last_successful_sync` | `datetime \| None` | Timestamp of the most recent successful API call |
| `last_failure` | `datetime \| None` | Timestamp of the most recent failure |
| `credential_status` | `str` | `present` / `missing` / `invalid` — never exposes credential values |

These fields are returned by the `GET /api/adapters/{adapter_id}/status` endpoint. No credential values, API keys, or tokens are ever included in the response.

### Common behaviors required of all write-capable adapters

- **Dry-run support**: every mutating method accepts `dry_run: bool`. When `True`, the adapter validates and logs the full payload but makes no network call.
- **Idempotency keys**: outbound write requests include a client-generated idempotency key. Re-sending the same key within the idempotency window returns the cached result without a second external action.
- **Rate-limit handling**: adapters catch rate-limit responses from the external API and raise a typed `RateLimitError` with a `retry_after` hint. The caller (service layer) decides whether to retry or surface to the user; adapters do not auto-retry.
- **Audit event generation**: every adapter call — whether successful, failed, dry-run, or rate-limited — emits an audit event to the audit log.
- **No silent fallback**: if a non-mock adapter is configured but fails, it raises a typed error; it does not silently fall back to mock behavior at runtime.

---

## Feature-Flag Gating

Adapter selection is determined at application startup by evaluating the following flags in order:

```
if DEMO_MODE=true → always use Mock/ManualInbox regardless of other flags
else if <PLATFORM>_ENABLED=false → use Disabled implementation
else if EXTERNAL_READS_ENABLED=false (for read calls) → use Mock
else if EXTERNAL_WRITES_ENABLED=false (for write calls) → read-only Official
else → use Official implementation (if credentials present and valid)
```

The resolved implementation is injected into the service layer via FastAPI's dependency injection. Services do not inspect feature flags directly; they receive an already-resolved adapter instance.

This means toggling a flag and restarting the application changes behavior without any code change, and test suites can inject mock implementations without patching global state.

---

## The Mock / Disabled / Official-Placeholder Pattern

Each integration point has three concrete implementations:

### Mock implementation

- Behaves exactly like the real adapter from the application's point of view.
- Returns realistic fixture data (freight offers, email messages, exchange rates, distances).
- All write methods accept and log the payload, then return a synthetic success response.
- Sets `mock_enabled: true` in its status metadata.
- Safe to use in development, demos, CI, and testing.

### Disabled implementation

- Raises `AdapterDisabledError` on any call.
- Returns a status payload indicating `read_enabled: false`, `write_enabled: false`.
- Used when a platform is not part of the current contract or has been explicitly turned off.
- Ensures a misconfigured flag cannot cause an accidental live call.

### Official placeholder (not yet implemented)

- Declares the correct interface and raises `NotImplementedError` on all methods.
- Contains documentation comments describing what the real implementation must do for each method.
- When real credentials are present and the platform is enabled but the Official implementation is still a placeholder, startup logs a clear warning and the system falls back to Disabled (not Mock) to prevent accidental fixture data from being treated as live data.

The `TIMOCOM_INTEGRATION_CHECKLIST.md` and `TRANSEU_INTEGRATION_CHECKLIST.md` files define what is needed to replace the placeholder with a real implementation.

---

## Dry-Run Rollout Steps

When enabling a real adapter for the first time:

1. Set the platform flag to `true` with all write flags still `false`.
2. Verify read operations return expected data by comparing against known manual imports.
3. Set `dry_run=True` on all write methods; review the audit log to confirm payloads are correctly formed.
4. Review a sample of dry-run ApprovalRequests end-to-end with the operator.
5. Set `EXTERNAL_WRITES_ENABLED=true` with one write method enabled at a time, starting with lowest-risk operations.
6. Monitor audit log and platform account for unexpected activity after each step.

---

## Manual Import Fallback

For every integration that supports live data ingestion, a manual import path exists:

- **Freight exchanges (TIMOCOM, Trans.eu)**: operator pastes or types freight details into the UI; the system parses and stores them as if they had arrived via the API.
- **Email**: `ManualInbox` adapter lets the operator paste email content or upload `.eml` / `.msg` files; the system processes them identically to live IMAP/OAuth-fetched messages.
- **Documents (CMR, invoices)**: operator uploads a PDF or image; the OCR provider extracts fields; the operator reviews and confirms before the data enters the domain model.
- **Exchange rates**: operator can enter rates manually when the Currency provider is disabled.
- **Distances/tolls**: operator can enter distance and toll estimates manually when the Distance/Toll provider is disabled.

Manual import data is tagged in the database with `source: manual` for audit and data-quality purposes.

---

## Provider Interfaces

In addition to the platform adapters (TIMOCOM, Trans.eu, Email), the following provider interfaces follow the same pattern:

### Distance Provider

**Capabilities**: `point_to_point_distance`, `route_distance`, `estimated_transit_time`

**Implementations**: `MockDistanceProvider` (returns fixture distances) | `DisabledDistanceProvider` | `OpenRouteServicePlaceholder` (Official placeholder)

**Notes**: Distances feed into cost and margin calculations in the rule-based service. The LLM never performs distance calculations.

### Toll Provider

**Capabilities**: `toll_estimate`, `toll_breakdown_by_country`

**Implementations**: `MockTollProvider` | `DisabledTollProvider` | `TollGuruPlaceholder` / similar

**Notes**: Toll estimates are displayed as non-binding guidance. ApprovalRequest payloads include the toll estimate with a `source` flag so the reviewer can judge reliability.

### Currency Provider

**Capabilities**: `spot_rate`, `rate_for_date`, `supported_pairs`

Supported pairs include at minimum EUR/PLN (the primary operating currencies).

**Implementations**: `MockCurrencyProvider` (returns fixed fixture rates) | `DisabledCurrencyProvider` | `ExchangeRateAPIPlaceholder`

**Notes**: Currency rates used in any ApprovalRequest are snapshotted at the time the request is created and included in the payload. Rate changes after creation do not alter a pending ApprovalRequest.

### Tracking Provider

**Capabilities**: `get_shipment_status`, `get_position`, `get_eta`

**Implementations**: `MockTrackingProvider` | `DisabledTrackingProvider` | Official placeholder

**Flag**: `TRACKING_ENABLED=false` by default.

**Notes**: Tracking data is read-only; it never triggers ApprovalRequests. It feeds the shipment status display only.

### OCR Provider

**Capabilities**: `extract_text`, `extract_structured_fields`, `classify_document_type`

**Implementations**: `MockOCRProvider` (returns fixture extracted fields) | `DisabledOCRProvider` | Local-model placeholder | Cloud-API placeholder

**Notes**: All OCR output is classified as untrusted content (see `SECURITY.md` §5). The operator must review and confirm extracted fields before they are committed to the domain model.

### LLM Provider

**Capabilities**: `classify_freight`, `suggest_rate`, `summarize_email`, `extract_key_dates`, `generate_message_draft`

**Flag**: `LOCAL_LLM_ENABLED=false`, `ANTHROPIC_LLM_ENABLED=false`

**Implementations**:

| Implementation | Description |
|---|---|
| `DeterministicMockLLM` | Returns scripted, fixture-based responses. Default. No network. |
| `ManualFallbackLLM` | Presents the LLM task to the operator as a manual input form. |
| `DisabledLLM` | Raises `LLMDisabledError`; features requiring LLM are hidden from UI. |
| `LocalOpenAICompatibleLLM` | Calls a local OpenAI-compatible endpoint (e.g., LM Studio, Ollama). Activated by `LOCAL_LLM_ENABLED=true`. |
| `AnthropicLLMPlaceholder` | Placeholder for Anthropic API integration. Activated by `ANTHROPIC_LLM_ENABLED=true`. Not yet implemented. |

**Prompt injection defense** is enforced at the LLM provider layer: all calls go through a prompt-construction helper that enforces the untrusted-data boundary. Direct prompt construction is not permitted in service code.

LLM outputs are validated by a schema validator before being returned to the service layer. The `ManualFallbackLLM` is used automatically when the configured LLM provider returns a schema-invalid response, ensuring the operator can always provide the missing information manually.
