# Freight Copilot — Demo Guide

This guide walks through five core workflows using the demo environment. All data is synthetic. No real exchanges, emails, or carriers are involved.

## Prerequisites

The app must be running. If it is not:

```bash
cd /home/user/doomdoja-ai/freight-copilot
make demo
```

Wait for the line:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Then open **http://127.0.0.1:8000** in your browser.

---

## UI Page Reference

| Page | URL | Purpose |
|---|---|---|
| Dashboard | `/` | Overview: active transports, pending approvals, recent alerts |
| Opportunity Inbox | `/opportunities` | Incoming freight orders and exchange offers, prioritised |
| Freight Detail | `/opportunities/{id}` | Full detail for one freight order with agent recommendations |
| Carrier Directory | `/carriers` | Searchable list of carriers with risk indicators |
| Active Transports | `/transports` | All in-progress shipments with status and ETA |
| Approval Inbox | `/approvals` | Pending ApprovalRequests awaiting human decision |
| Documents | `/documents` | Transport documents with completion status |
| Knowledge Base | `/kb` | Stored operational notes, lane history, carrier notes |
| Settings | `/settings` | Feature flags, pricing config, notification preferences |

---

## Workflow A — Intake and Prioritisation

**Scenario:** Three new freight orders have arrived (two from email simulation, one from a TIMOCOM fixture). The Intake / Inbox Dispatcher has classified and scored them. You review and prioritise.

### Steps

1. Open **http://127.0.0.1:8000**. The Dashboard shows a summary card: "3 new opportunities in inbox."

2. Click **Opportunity Inbox** in the left navigation, or go to **http://127.0.0.1:8000/opportunities**.

3. The inbox shows three rows, sorted by the agent's priority score (highest first). Each row shows:
   - Origin → Destination
   - Load type and weight
   - Required loading date
   - Priority score (0–100) with a colour indicator (red = urgent, amber = normal, green = low)
   - Source (e.g., "TIMOCOM fixture", "Email import")

4. Click the top row (highest priority order) to open **Freight Detail** at `/opportunities/{id}`.

5. On the Freight Detail page, review:
   - **Order summary** (route, dates, load description)
   - **Agent recommendations panel**: the Pricing & Margin agent has proposed a sell rate and expected margin; the Carrier Matching agent has listed the top 3 carriers for this lane
   - **Confidence indicator** next to each recommendation (e.g., "Confidence: 0.87")
   - **Missing fields** listed if the agent could not populate everything (e.g., "exact unloading address not provided")

6. The order is not yet assigned. Two buttons are visible:
   - **"Initiate carrier search"** — creates a new ApprovalRequest of type `CARRIER_ENQUIRY_DRAFT` with pre-filled message drafts
   - **"Park order"** — moves it to a "parked" queue

7. Click **"Initiate carrier search"**. A confirmation banner appears: "Approval request created — review in Approval Inbox."

   Note: no message has been sent yet. An ApprovalRequest is created; the actual send requires your explicit approval.

---

## Workflow B — Carrier Search and Selection

**Scenario:** Continuing from Workflow A. You have an ApprovalRequest for a carrier enquiry. You review the draft messages, approve one, and the system records the action.

### Steps

1. Navigate to **Approval Inbox** at **http://127.0.0.1:8000/approvals**.

2. Find the request created in Workflow A (type: `CARRIER_ENQUIRY_DRAFT`, status: `PENDING`). Click it.

3. The approval detail page shows:
   - **What will happen if approved**: "Draft enquiry email will be queued for sending to 3 carriers" (note: in demo mode with `EMAIL_ENABLED=false`, this is a logged dry-run)
   - **Draft email content** for each carrier: subject, body in the detected language (Polish or English depending on carrier fixture)
   - **Carrier risk summary**: each carrier's document status (all green in demo data)
   - **Compliance check result**: the Compliance & Safety Supervisor agent has confirmed no cabotage or ADR issues

4. Review the draft email for Carrier 1. If you want to edit the text, click **"Edit draft"** — a text area opens with the draft content. Make any changes and click **"Save draft"**.

5. Click **"Approve"** for Carrier 1's enquiry. A modal asks: "Confirm: approve enquiry to [Carrier Name]?" Click **"Confirm"**.

6. The ApprovalRequest for Carrier 1 changes to status `APPROVED` → `EXECUTED` (in demo mode: `DRY_RUN`). A log entry appears: "Action executed (dry-run): email queued."

7. Click **"Reject"** for Carrier 3's enquiry (e.g., you prefer only two enquiries). A reason field appears; type "Rate too high on this lane" and click **"Confirm rejection"**.

8. Return to the Dashboard. The active transport count has not yet changed — a transport is only created when a carrier confirms and you approve the booking.

---

## Workflow C — Transport Monitoring with Delay Alert

**Scenario:** An active transport is in progress. The Transport Monitoring agent has detected that the truck is behind schedule and has raised a delay alert. You review the alert and approve a customer notification draft.

### Steps

1. Navigate to **Active Transports** at **http://127.0.0.1:8000/transports**.

2. The list shows several active shipments. One row has a red **"DELAY ALERT"** badge. Click it to open the transport detail.

3. The transport detail page shows:
   - **Timeline**: planned loading, planned arrival vs. current status
   - **Alert detail**: "ETA deviation: +4 hours. Last status update: [timestamp]. Carrier has not confirmed revised ETA."
   - **Agent recommendation**: "Draft customer delay notification" (Communication Drafting agent output)
   - A pre-generated draft notification in the customer's language (Polish in this demo)

4. Click **"Create approval request for delay notification"**. This creates an ApprovalRequest of type `CUSTOMER_DELAY_NOTIFICATION`.

5. Navigate to **Approval Inbox** at **http://127.0.0.1:8000/approvals**. Find the new request.

6. Review the draft notification. It contains:
   - Reference to the correct order number
   - Revised estimated delivery date/time
   - Apology and explanation (template-based in deterministic mode)

7. Click **"Edit draft"** if you want to personalise the message, then **"Approve"**.

8. The action is executed (dry-run in demo). Return to **Active Transports**: the transport row now shows status "DELAY NOTIFIED — customer informed [timestamp]."

---

## Workflow D — Document Completion

**Scenario:** A transport has been completed. The Document Controller agent has identified that the proof of delivery (POD) is missing and the carrier's insurance certificate is expiring in 14 days.

### Steps

1. Navigate to **Documents** at **http://127.0.0.1:8000/documents**.

2. The page shows a list of recent transports with document completion indicators. One transport shows:
   - CMR: green checkmark
   - Invoice: green checkmark
   - POD: red **"MISSING"**

3. Click the transport row to open its document detail.

4. The Document Controller agent panel shows:
   - "POD not received. Required for invoice settlement."
   - "Carrier insurance certificate expires in 14 days. Renewal reminder recommended."

5. Click **"Request POD from carrier"**. This creates an ApprovalRequest of type `DOCUMENT_REQUEST_EMAIL` with a pre-drafted message to the carrier.

6. Navigate to **Approval Inbox** and approve the document request (or review and edit the draft first).

7. Back on the document page, an **"Upload POD"** button is visible. Click it and select any PDF file from your machine (demo accepts any file without validation on upload).

8. After upload, the POD row changes to "RECEIVED — pending review." In a real workflow the Document Controller would re-run to validate the uploaded file's fields against the CMR.

9. Navigate to **Carrier Directory** at **http://127.0.0.1:8000/carriers**. Find the carrier from this transport. A yellow **"Certificate expiring soon"** badge is visible. Click the carrier row to see the expiry details and a button to create an approval request for a renewal reminder.

---

## Workflow E — Knowledge Accumulation

**Scenario:** You have just negotiated a good rate on a Warsaw–Milan lane. You want to record this in the Knowledge Base so future pricing recommendations benefit from it.

### Steps

1. Navigate to **Knowledge Base** at **http://127.0.0.1:8000/kb**.

2. The page shows existing knowledge entries (seeded from fixtures): lane notes, carrier observations, and past decisions. Use the search box to search for "Milan" — one existing entry appears from the demo data.

3. Click **"Add knowledge entry"**.

4. Fill in the form:
   - **Title**: "Warsaw–Milan FTL rate — June 2026"
   - **Type**: select "Lane rate" from the dropdown
   - **Content**: "Negotiated buy rate: 1.10 EUR/km. Carrier: Demo Carrier GmbH. Load: 24t standard trailer. Transit time: 3 days. Notes: carrier available most Mondays, prefers payment within 14 days."
   - **Tags**: `lane:WAW-MXP`, `carrier:demo-gmbh`, `rate:eur-per-km`

5. Click **"Save"**. The entry appears in the list with a timestamp.

6. Now navigate back to **Opportunity Inbox** and open any freight order for a Warsaw–Italy route. Scroll to the **Knowledge Base matches** panel on the Freight Detail page.

7. The panel shows: "1 related knowledge entry found: 'Warsaw–Milan FTL rate — June 2026'." The Pricing & Margin agent has used this entry to inform its rate proposal (shown as: "Rate informed by KB entry #[id], confidence adjusted to 0.92").

8. Navigate to **Settings** at **http://127.0.0.1:8000/settings** to see the current feature flag state. Observe that all external flags are `false`. The demo mode indicator confirms: "DEMO_MODE: enabled — all data is synthetic."

---

## Tips for Demo Facilitators

- All demo data is reset by running `make reseed` (see RUNBOOK.md).
- The Approval Inbox is the central control point — every sensitive workflow converges there.
- The confidence score on agent outputs is intentionally visible to show the operator when to trust automation and when to apply their own judgment.
- The "dry-run" label on executed actions in demo mode is deliberate: it confirms the workflow is complete without making any real external calls.
