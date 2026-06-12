# Employer Discovery Questions

## Purpose

This document contains the full list of questions to ask when joining the company. Answers to these questions are required to configure the system correctly, enable real integrations, and ensure compliance with company policy, platform contracts, and GDPR obligations.

Questions are grouped by topic. Gather answers from the relevant stakeholders (operations manager, IT, finance, legal/compliance, platform account managers).

---

## Group 1: Platform Contracts and API Access

### 1.1 TIMOCOM

1. Does the company have an active TIMOCOM API contract (separate from the standard web UI subscription)?
2. If yes: which API modules are included — freight exchange search, freight offer/load insertion, transport order management, shipment tracking/telematic data exchange, price overviews/rate benchmarking, carrier/company verification and rating data?
3. Are there any API scopes or modules the company explicitly does not have access to?
4. What authentication method is required (API key, OAuth 2.0, client certificate)?
5. Is a sandbox / test environment available under this contract?
6. Who holds or can retrieve the API credentials (client ID, secret, API key)?
7. Are there contractual restrictions on automated API calls — rate limits, permitted use cases, data retention obligations, prohibition on scraping?
8. Who is the TIMOCOM account manager or technical contact for API questions?

### 1.2 Trans.eu

9. Does the company have an active Trans.eu API access agreement?
10. Which API scopes are enabled: creating freight offers, publishing/unpublishing offers, updating offers, cancelling publication, archiving, reading offer status/history, received proposals (carrier bids), price negotiation, accepted-freight details, monitoring tasks?
11. What authentication method is required?
12. Is a sandbox / test environment available?
13. Who holds the Trans.eu API credentials?
14. Are there call frequency or volume limits under the contract?
15. Who is the Trans.eu technical or account contact for API questions?

### 1.3 Other Platforms

16. Does the company use any other freight exchanges or load boards beyond TIMOCOM and Trans.eu (e.g., Teleroute, Wtransnet, 123Cargo)?
17. If yes, are API contracts available for any of them?

---

## Group 2: Existing Internal Systems

### 2.1 Transport Management System (TMS)

18. Does the company currently use a TMS? If so, which one (product name and version)?
19. Does the TMS have an API or data export capability?
20. Is the TMS the authoritative system for transport orders, or does it duplicate data from TIMOCOM/Trans.eu?
21. Are there plans to replace or upgrade the TMS in the near future?

### 2.2 Email and Communication

22. What email provider does the company use (Microsoft 365 / Exchange, Google Workspace, other)?
23. Is API access to the mailbox available (Microsoft Graph API, Gmail API)?
24. Which email address(es) are used for freight and carrier communications?
25. Are there any restrictions on automated reading or sending of emails from company accounts?

### 2.3 Finance and Invoicing

26. What system is used for invoicing customers and paying carriers?
27. Is there an API or export format available?
28. Should Freight Copilot ever create draft invoices, or is that strictly handled in the finance system?

---

## Group 3: AI Tools and Data Policy

29. Which AI or automation tools has the company already approved for operational use?
30. Is the use of cloud-hosted AI (e.g., Anthropic Claude API, OpenAI) approved for processing operational freight data?
31. Can a locally-hosted AI model process operational data on company infrastructure (on-premises or company VPC)?
32. Which specific categories of data may never leave company infrastructure under any circumstances? (Examples: customer names and contact details, carrier rates and margins, transport order details, financial data.)
33. Are there specific data categories that have been reviewed and approved for cloud AI processing?
34. Is there a company AI usage policy or information security policy that governs this?

---

## Group 4: GDPR and Compliance

35. Who is the company's Data Protection Officer (DPO) or responsible person for GDPR compliance?
36. What personal data categories does the company process in freight operations? (Carrier contact persons, customer contact persons, driver data, vehicle data.)
37. Where must this personal data reside — EU only, specific country, or no restriction?
38. What is the required retention period for operational data (freight records, communications)?
39. What is the required retention period for financial documents (invoices, CMR documents)?
40. Does the company have data processing agreements with current platform providers (TIMOCOM, Trans.eu)?
41. Are there any ongoing regulatory audits or compliance obligations relevant to data handling?
42. Has the company performed a Data Protection Impact Assessment (DPIA) for any automated freight processing tools?

---

## Group 5: Operational Workflow and Business Rules

### 5.1 Languages and Trade Lanes

43. What are the primary operating languages for freight communications? (The system currently supports PL/EN/IT/DE.)
44. Are there additional languages regularly used with carriers or customers?
45. What are the main trade lanes (country pairs) the company handles most frequently?
46. Are there any countries or routes the company avoids or has specific handling rules for?

### 5.2 Vehicle and Cargo Types

47. What vehicle types are most commonly used (standard tautliner/curtainsider, mega/jumbo trailer, flatbed, refrigerated/reefer, container, full truck load, groupage/LTL)?
48. Are there cargo types the company regularly handles that require special handling (ADR/dangerous goods, oversized, temperature-controlled, high-value)?
49. Does the company have preferred vehicle body types or carrier certifications it requires?

### 5.3 Pricing and Margin

50. How does the company typically determine sell rates to customers (fixed tariff, market-based, cost-plus margin)?
51. What is the typical target margin range (a rough percentage or fixed amount per route is sufficient for system calibration)?
52. Are there customers with fixed rate agreements or frame contracts that should take precedence over market rates?
53. Which currency is used for customer invoicing (EUR, PLN, or both)? What about carrier payments?

---

## Group 6: Carrier Management

54. Does the company maintain a carrier database? If so, in what system and format?
55. What fields are tracked per carrier (company name, VAT number, insurance details, vehicle types, certifications, performance history)?
56. Is there a carrier blacklist, and where is it maintained?
57. What is the mandatory carrier verification process before placing a first order? (Documents required: insurance certificate, carrier license, VIES VAT check, etc.)
58. Who is authorized to approve a new carrier for use?
59. Who maintains and updates the carrier blacklist?
60. Are there preferred carrier tiers or preferred carriers for specific routes?

---

## Group 7: Approval and Escalation Rules

61. Which specific actions require supervisor or manager approval (rate confirmations above a threshold, new customer setup, new carrier first order, claims, cancellations)?
62. What is the threshold (amount or other condition) that triggers a higher-level approval?
63. Who approves freight rates — the operator alone, or does a manager need to sign off?
64. Who handles carrier claims and disputes?
65. Who approves new customers (credit check, contract, etc.)?
66. What actions are strictly forbidden for the operator to take autonomously?
67. Is there an after-hours support arrangement, and if so, what actions can be taken without a supervisor available?

---

## Group 8: KPIs and Reporting

68. Which KPIs are most important to the company currently? (Examples: margin per shipment, on-time delivery rate, carrier fill rate, average rate per km, revenue per trade lane.)
69. How is current operational performance tracked — Excel, TMS reports, manual?
70. What reports does management currently receive regularly, and at what frequency?
71. Are there any KPI targets or benchmarks the system should track against?

---

## Group 9: Historical Data and Onboarding

72. Is there exportable historical freight data (past orders, rates, carrier performance) that could be imported for context and benchmarking?
73. In what format is historical data available (Excel, CSV, TMS export, PDF)?
74. How far back does relevant historical data go?
75. Are there existing rate cards or pricing tables that should be loaded into the system?

---

## Group 10: IT and Infrastructure

76. Where will Freight Copilot run — operator's workstation (local only), company server, or cloud VM?
77. What operating system is available on the deployment target?
78. Is there a company VPN requirement for accessing internal resources from the deployment host?
79. Is there a company policy on approved open-source software or Python packages?
80. Who is responsible for IT support at the company (internal IT team, external provider, or self-managed)?
81. Are there firewall rules that would block outbound HTTPS calls to TIMOCOM or Trans.eu APIs?
82. Is a production-grade database server available (PostgreSQL), or will SQLite be used?
83. What is the backup policy for operational data?

---

## Notes for the Onboarding Meeting

- Bring this document as a printed or shared checklist.
- Not all questions need immediate answers; prioritize Groups 1, 3, 5, and 7 for the first meeting.
- Answers to Groups 1 and 2 unlock the integration enabling checklists (`TIMOCOM_INTEGRATION_CHECKLIST.md`, `TRANSEU_INTEGRATION_CHECKLIST.md`).
- Answers to Group 3 determine whether cloud AI features can be enabled.
- Answers to Groups 4 and 9 should involve the DPO or legal counsel if one is available.
