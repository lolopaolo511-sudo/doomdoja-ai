"""Carrier Risk & Verification agent.

Supports safer contractor selection via a manual-review checklist over the
carrier's data and documents. Never marks a company "safe" because a single
field is present; always exposes source, timestamps, missing info and reasoning.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .base import AgentResult, BaseAgent

CHECKLIST = [
    "company_identity",
    "vat_number",
    "contact_consistency",
    "carrier_license",
    "insurance_ocp",
    "internal_blacklist",
    "bank_account_stable",
    "documents_present",
    "profile_freshness",
]


class CarrierRiskAgent(BaseAgent):
    name = "carrier_risk"

    def assess(self, carrier: dict, documents: list[dict], risk_flags: list[dict]) -> AgentResult:
        now = datetime.now(UTC)
        findings: list[str] = []
        missing: list[str] = []
        results: dict[str, str] = {}

        results["company_identity"] = "ok" if carrier.get("legal_name") else "missing"
        results["vat_number"] = "ok" if carrier.get("vat_number") else "missing"
        if not carrier.get("vat_number"):
            missing.append("vat_number")

        # Insurance / OCP validity
        insurance = [d for d in documents if d.get("doc_type") in {"insurance", "ocp"}]
        if not insurance:
            results["insurance_ocp"] = "missing"
            missing.append("insurance/ocp document")
            findings.append("no insurance/OCP document on file")
        else:
            expired = [
                d for d in insurance if d.get("expiry_date") and self._aware(d["expiry_date"]) < now
            ]
            if expired:
                results["insurance_ocp"] = "expired"
                findings.append("insurance/OCP document expired")
            else:
                results["insurance_ocp"] = "ok"

        # License
        has_license = any(d.get("doc_type") == "license" for d in documents)
        results["carrier_license"] = "ok" if has_license else "missing"
        if not has_license:
            missing.append("carrier_license")

        # Risk flags (blacklist, bank changes, incidents)
        flag_kinds = {f.get("flag") for f in risk_flags}
        results["internal_blacklist"] = "flagged" if "blacklist" in flag_kinds else "ok"
        if any("bank" in (f.get("flag") or "") for f in risk_flags):
            results["bank_account_stable"] = "suspicious"
            findings.append("suspicious bank-detail change reported")
        else:
            results["bank_account_stable"] = "ok"
        for f in risk_flags:
            findings.append(f"flag: {f.get('flag')} ({f.get('severity')})")

        # Profile freshness
        last = carrier.get("last_cooperation_date")
        results["profile_freshness"] = "stale" if not last else "ok"

        # Derive risk level — conservative: any high finding escalates.
        level = "low"
        if not missing and not findings:
            level = "low"
        if missing:
            level = "medium"
        if any("expired" in f or "suspicious" in f for f in findings) or "blacklist" in flag_kinds:
            level = "high"
        if "blacklist" in flag_kinds:
            level = "blocked"

        return self._result(
            summary=(
                f"Carrier risk: {level}. "
                f"{len(missing)} missing item(s), {len(findings)} finding(s). "
                "Never treated as safe on a single field; human review required."
            ),
            output={
                "risk_level": level,
                "checklist": results,
                "findings": findings,
                "missing": missing,
                "source": carrier.get("verification_source"),
                "timestamp": now.isoformat(),
                "reviewer_required": True,
            },
            confidence=0.7 if not missing else 0.5,
            missing_fields=missing,
            factors=findings or ["clean"],
        )

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
