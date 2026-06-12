"""Transport Monitoring agent.

Tracks active shipments and highlights exceptions from milestones / mock
tracking events. Produces alerts and recommended human actions, plus prepared
draft messages — but never acts autonomously.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .base import AgentResult, BaseAgent

MILESTONE_ORDER = [
    "transport_created",
    "carrier_assigned",
    "vehicle_confirmed",
    "pickup_scheduled",
    "arrived_at_pickup",
    "loading_started",
    "departed_pickup",
    "in_transit",
    "arrived_at_delivery",
    "unloading_started",
    "delivered",
    "pod_requested",
    "pod_received",
    "transport_closed",
]


class MonitoringAgent(BaseAgent):
    name = "monitoring"

    def evaluate(self, shipment: dict, milestones: list[dict]) -> AgentResult:
        now = datetime.now(UTC)
        alerts: list[dict] = []
        done = {m["name"] for m in milestones if m.get("occurred_at")}

        # Determine current and next milestone.
        current = None
        for m in MILESTONE_ORDER:
            if m in done:
                current = m
        idx = MILESTONE_ORDER.index(current) + 1 if current in MILESTONE_ORDER else 0
        next_milestone = MILESTONE_ORDER[idx] if idx < len(MILESTONE_ORDER) else None

        # Exception detection on expected vs actual times.
        for m in milestones:
            exp = m.get("expected_at")
            occ = m.get("occurred_at")
            if exp and not occ and self._aware(exp) < now:
                alerts.append(
                    {
                        "kind": f"missing_{m['name']}",
                        "severity": "high",
                        "message": f"Expected '{m['name']}' has not been confirmed.",
                        "recommended_action": "Request status from carrier.",
                    }
                )

        # Pickup delay
        if "pickup_scheduled" in done and "arrived_at_pickup" not in done:
            sched = next((m for m in milestones if m["name"] == "pickup_scheduled"), None)
            if sched and sched.get("occurred_at") and self._aware(sched["occurred_at"]) < now:
                alerts.append(
                    {
                        "kind": "pickup_delay",
                        "severity": "high",
                        "message": "Carrier has not confirmed arrival at pickup.",
                        "recommended_action": "Send carrier status request and warn customer.",
                    }
                )

        # Missing POD after delivery
        if "delivered" in done and "pod_received" not in done:
            alerts.append(
                {
                    "kind": "missing_pod",
                    "severity": "medium",
                    "message": "Delivered but POD not yet received.",
                    "recommended_action": "Request signed POD/CMR from carrier.",
                }
            )

        state = shipment.get("state", "created")
        return self._result(
            summary=(
                f"Shipment at '{current or 'start'}'. {len(alerts)} alert(s). "
                "Human approval required for any outbound action."
            ),
            output={
                "current_state": current or state,
                "next_expected_milestone": next_milestone,
                "alerts": alerts,
                "timeline": [m["name"] for m in milestones if m.get("occurred_at")],
                "recommended_human_action": (
                    alerts[0]["recommended_action"] if alerts else "Monitor."
                ),
            },
            confidence=0.8,
            factors=[a["kind"] for a in alerts] or ["nominal"],
        )

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
