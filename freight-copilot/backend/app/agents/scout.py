"""Freight Opportunity Scout agent.

Prioritises which freight opportunities deserve attention using a transparent,
configurable, rule-based 0-100 score. The weights are editable in settings;
the score is explicitly NOT market intelligence and says so.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .base import AgentResult, BaseAgent

# Default, editable weights (sum loosely to 100 before normalisation).
DEFAULT_WEIGHTS = {
    "data_completeness": 20,
    "margin_potential": 25,
    "carrier_findability": 15,
    "route_desirability": 15,
    "urgency": 10,
    "complexity_penalty": -10,
    "uncertainty_penalty": -10,
}

# Lanes the (demo) forwarder considers desirable.
DESIRABLE_LANES = {"PL-IT", "PL-DE", "IT-PL", "DE-PL", "PL-CZ", "CZ-PL"}


class ScoutAgent(BaseAgent):
    name = "scout"

    def __init__(self, provider=None, weights: dict | None = None) -> None:
        super().__init__(provider)
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def score(self, offer: dict, margin_pct: float | None = None) -> AgentResult:
        factors: list[str] = []
        unknowns: list[str] = []
        contributions: dict[str, float] = {}

        # Data completeness
        critical = ["origin_city", "dest_city", "pickup_date", "weight_kg", "vehicle_type"]
        present = sum(1 for f in critical if offer.get(f))
        completeness = present / len(critical)
        contributions["data_completeness"] = self.weights["data_completeness"] * completeness
        if completeness < 1:
            unknowns.append("incomplete offer data")

        # Margin potential
        if margin_pct is not None:
            m = max(0.0, min(margin_pct / 20.0, 1.0))  # 20%+ margin => full marks
            contributions["margin_potential"] = self.weights["margin_potential"] * m
            factors.append(f"margin≈{margin_pct:.0f}%")
        else:
            contributions["margin_potential"] = self.weights["margin_potential"] * 0.4
            unknowns.append("margin not yet estimated")

        # Carrier findability (proxy: common vehicle type + known lane)
        lane = self._lane(offer)
        findable = 0.5
        if offer.get("vehicle_type") in {"tautliner", "box", "mega", None}:
            findable += 0.3
        if lane in DESIRABLE_LANES:
            findable += 0.2
        findable = min(findable, 1.0)
        contributions["carrier_findability"] = self.weights["carrier_findability"] * findable

        # Route desirability
        route = 1.0 if lane in DESIRABLE_LANES else 0.5
        contributions["route_desirability"] = self.weights["route_desirability"] * route
        if lane:
            factors.append(f"lane:{lane}")

        # Urgency (pickup soon => higher attention)
        urgency = self._urgency(offer)
        contributions["urgency"] = self.weights["urgency"] * urgency

        # Complexity penalty (ADR / reefer / temperature)
        complexity = 0.0
        if offer.get("adr_required"):
            complexity += 0.5
            factors.append("ADR")
        if offer.get("vehicle_type") in {"reefer", "frigo"} or offer.get("temperature_c"):
            complexity += 0.5
            factors.append("temperature-controlled")
        contributions["complexity_penalty"] = self.weights["complexity_penalty"] * min(
            complexity, 1.0
        )

        # Uncertainty penalty
        uncertainty = 1.0 - completeness
        contributions["uncertainty_penalty"] = self.weights["uncertainty_penalty"] * uncertainty

        total = sum(contributions.values())
        total = int(max(0, min(round(total), 100)))

        priority = self._priority(total, offer)
        next_action, questions = self._next_action(priority, offer, unknowns)

        return self._result(
            summary=(
                f"Opportunity score {total}/100 → {priority}. "
                "Rule-based heuristic, not live market data."
            ),
            output={
                "score": total,
                "breakdown": {k: round(v, 1) for k, v in contributions.items()},
                "priority": priority,
                "explanation": factors,
                "unknowns": unknowns,
                "recommended_next_action": next_action,
                "suggested_questions": questions,
            },
            confidence=round(0.5 + 0.4 * completeness, 2),
            missing_fields=[f for f in critical if not offer.get(f)],
            factors=factors,
        )

    @staticmethod
    def _lane(offer: dict) -> str | None:
        oc, dc = offer.get("origin_country"), offer.get("dest_country")
        return f"{oc}-{dc}" if oc and dc else None

    @staticmethod
    def _urgency(offer: dict) -> float:
        pd = offer.get("pickup_date")
        if not isinstance(pd, datetime):
            return 0.5
        if pd.tzinfo is None:
            pd = pd.replace(tzinfo=UTC)
        days = (pd - datetime.now(UTC)).days
        if days <= 0:
            return 1.0
        if days <= 1:
            return 0.9
        if days <= 3:
            return 0.6
        return 0.3

    @staticmethod
    def _priority(score: int, offer: dict) -> str:
        if score >= 75:
            return "contact_now"
        if score >= 55:
            return "review_soon"
        if score >= 35:
            return "watch"
        if score >= 20:
            return "low_priority"
        return "reject_candidate"

    @staticmethod
    def _next_action(priority: str, offer: dict, unknowns: list[str]):
        questions: list[str] = []
        if not offer.get("unloading_method"):
            questions.append("What is the unloading method at destination?")
        if not offer.get("weight_kg"):
            questions.append("What is the exact cargo weight?")
        if not offer.get("customer_rate"):
            questions.append("What customer rate is offered?")
        action = {
            "contact_now": "Contact customer and start carrier search now.",
            "review_soon": "Review and request missing details, then score carriers.",
            "watch": "Keep on watchlist; revisit if capacity is available.",
            "low_priority": "Deprioritise unless margin improves.",
            "reject_candidate": "Likely reject; confirm there is no hidden value.",
        }[priority]
        return action, questions
