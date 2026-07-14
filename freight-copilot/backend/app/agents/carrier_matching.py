"""Carrier Matching agent.

Shortlists external carriers for a freight order from the local carrier
database. Advisory only: ranking never auto-selects a carrier, and any carrier
with a blocking risk is excluded/flagged. Human verification is always required.
"""

from __future__ import annotations

from .base import AgentResult, BaseAgent


class CarrierMatchingAgent(BaseAgent):
    name = "carrier_matching"

    def shortlist(self, offer: dict, carriers: list[dict]) -> AgentResult:
        lane = self._lane(offer)
        vt = offer.get("vehicle_type")
        ranked = []
        for c in carriers:
            score = 0
            why: list[str] = []
            disq: list[str] = []

            # Hard disqualifiers
            if c.get("risk_level") == "blocked":
                disq.append("carrier is blocked")
            if lane and lane in (c.get("blacklisted_lanes") or []):
                disq.append(f"lane {lane} is blacklisted for this carrier")

            # Lane match
            if lane and lane in (c.get("routes_served") or []):
                score += 30
                why.append(f"serves lane {lane}")
            if lane and lane in (c.get("preferred_lanes") or []):
                score += 10
                why.append("preferred lane")

            # Vehicle suitability
            if vt and vt in (c.get("vehicle_types") or []):
                score += 20
                why.append(f"has {vt}")
            elif vt:
                disq.append(f"no {vt} vehicle listed")

            # Capability requirements
            if offer.get("adr_required") and not c.get("adr_capable"):
                disq.append("ADR required but carrier not ADR-capable")
            elif offer.get("adr_required"):
                score += 5
                why.append("ADR capable")
            if (vt in {"reefer", "frigo"} or offer.get("temperature_c") is not None) and not c.get(
                "reefer_capable"
            ):
                disq.append("reefer required but carrier not reefer-capable")

            # Reliability / cooperation
            rel = c.get("reliability_rating") or 0
            score += min(rel, 5) * 3
            if rel >= 4:
                why.append("reliable history")
            if c.get("completed_transports", 0) > 0:
                score += 5

            # Risk-aware adjustment (not a disqualifier unless blocked)
            if c.get("risk_level") in {"high"}:
                score -= 20
                why.append("elevated risk — verify before use")

            if disq:
                score = max(0, score - 50)

            ranked.append(
                {
                    "carrier_id": c.get("id"),
                    "legal_name": c.get("legal_name"),
                    "score": max(0, min(score, 100)),
                    "explanation": why,
                    "disqualifiers": disq,
                    "risk_level": c.get("risk_level", "unknown"),
                }
            )

        ranked.sort(key=lambda r: (not r["disqualifiers"], r["score"]), reverse=True)
        top = ranked[:8]
        eligible = [r for r in top if not r["disqualifiers"]]

        return self._result(
            summary=(
                f"Shortlisted {len(eligible)} eligible of {len(carriers)} carriers "
                "(advisory only; human verification required before contact)."
            ),
            output={
                "shortlist": top,
                "eligible_count": len(eligible),
                "human_verification_required": True,
                "lane": lane,
            },
            confidence=0.6 if eligible else 0.4,
            missing_fields=[] if vt else ["vehicle_type"],
            factors=[f"lane:{lane}", f"vehicle:{vt}"],
        )

    @staticmethod
    def _lane(offer: dict) -> str | None:
        oc, dc = offer.get("origin_country"), offer.get("dest_country")
        return f"{oc}-{dc}" if oc and dc else None
