"""Document Controller agent.

Operational document completeness checks (NOT legal validation). Determines
which required documents are missing for a shipment and flags inconsistencies.
Every result is explicitly labelled an operational check only.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .base import AgentResult, BaseAgent

# Documents typically required to close a delivered road-freight shipment.
REQUIRED_FOR_CLOSE = ["transport_order", "cmr", "pod", "invoice"]


class DocumentControllerAgent(BaseAgent):
    name = "document_controller"

    def check(self, shipment: dict, documents: list[dict]) -> AgentResult:
        present_types = {d["doc_type"] for d in documents if d.get("status") != "rejected"}
        missing = [d for d in REQUIRED_FOR_CLOSE if d not in present_types]

        inconsistencies: list[str] = []
        now = datetime.now(UTC)
        for d in documents:
            exp = d.get("expiry_date")
            if exp and self._aware(exp) < now:
                inconsistencies.append(f"{d['doc_type']} is expired")
            if d.get("readable") is False:
                inconsistencies.append(f"{d['doc_type']} marked unreadable")
            if d.get("missing_pages"):
                inconsistencies.append(f"{d['doc_type']} has missing pages")
            if d.get("doc_type") in {"cmr", "pod"} and d.get("signatures_present") is False:
                inconsistencies.append(f"{d['doc_type']} is unsigned")

        completeness = "complete" if not missing else "incomplete"
        review_needed = bool(missing or inconsistencies)

        return self._result(
            summary=(
                f"Operational document check: {completeness}. "
                f"{len(missing)} missing, {len(inconsistencies)} issue(s). "
                "This is an operational check only — not legal validation."
            ),
            output={
                "completeness": completeness,
                "missing": missing,
                "inconsistencies": inconsistencies,
                "review_needed": review_needed,
                "explanation": (
                    "Missing: " + ", ".join(missing) if missing else "All required docs present."
                ),
            },
            confidence=0.85,
            missing_fields=missing,
            factors=inconsistencies or ["ok"],
        )

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
