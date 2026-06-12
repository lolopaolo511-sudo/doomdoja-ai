"""Personal Operational Knowledge Base agent.

Builds a private, searchable knowledge base of operational lessons. Suggests
notes after events but requires human approval before model-suggested notes
are saved. Marks provenance (confirmed/observed/user_entered/model_suggested/
disputed) — speculative statements are never stored as facts.
"""

from __future__ import annotations

from .base import AgentResult, BaseAgent


class KnowledgeBaseAgent(BaseAgent):
    name = "knowledge_base"

    def suggest(self, shipment: dict, context: dict | None = None) -> AgentResult:
        context = context or {}
        suggestions: list[dict] = []

        route = f"{shipment.get('origin', '?')} → {shipment.get('destination', '?')}"
        carrier_name = context.get("carrier_name")

        if context.get("had_delay"):
            suggestions.append(
                {
                    "title": f"Delay pattern on {route}",
                    "body": f"Observed a delay on {route}. Confirm if recurring before "
                    "treating as a pattern.",
                    "tags": ["route", "delay"],
                    "provenance": "model_suggested",
                    "confidence": 0.5,
                }
            )
        if carrier_name and context.get("carrier_ok"):
            suggestions.append(
                {
                    "title": f"{carrier_name} performance",
                    "body": f"{carrier_name} completed {route} as agreed. Candidate for "
                    "preferred list on this lane (needs one more confirmation).",
                    "tags": ["carrier"],
                    "provenance": "model_suggested",
                    "confidence": 0.55,
                }
            )
        if context.get("warehouse_delay"):
            suggestions.append(
                {
                    "title": f"Warehouse delay at {context.get('warehouse', 'destination')}",
                    "body": "Unloading took longer than planned. Verify typical dwell time.",
                    "tags": ["warehouse", "delay"],
                    "provenance": "model_suggested",
                    "confidence": 0.5,
                }
            )

        return self._result(
            summary=(
                f"{len(suggestions)} knowledge note(s) suggested. "
                "All require human approval before saving; marked model_suggested."
            ),
            output={"suggestions": suggestions, "requires_approval": True},
            confidence=0.5,
            factors=[s["title"] for s in suggestions] or ["none"],
        )

    @staticmethod
    def search(notes: list[dict], query: str) -> list[dict]:
        q = (query or "").lower().strip()
        if not q:
            return notes
        out = []
        for n in notes:
            hay = " ".join(
                [n.get("title", ""), n.get("body", ""), " ".join(n.get("tags", []))]
            ).lower()
            if q in hay:
                out.append(n)
        return out
