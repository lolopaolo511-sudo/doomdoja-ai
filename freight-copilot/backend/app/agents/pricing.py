"""Pricing & Margin agent.

Estimates whether an opportunity may be commercially attractive using an
editable rules table (baseline EUR/km, multipliers, toll/deadhead/weekend
adjustments). NEVER claims to be a live market rate — every output is labelled
as a rule-based estimate with explicit assumptions and a sensitivity range.
"""

from __future__ import annotations

from .base import AgentResult, BaseAgent

# Baseline EUR/km by region pair (illustrative, editable in settings).
DEFAULT_RULES = {
    "base_eur_per_km": 1.20,
    "vehicle_multiplier": {"reefer": 1.35, "frigo": 1.35, "mega": 1.1, "box": 1.05},
    "adr_multiplier": 1.15,
    "reefer_multiplier": 1.30,
    "urgency_multiplier": 1.10,
    "weekend_multiplier": 1.10,
    "toll_per_km": 0.12,
    "deadhead_pct": 0.10,
    "low_confidence_penalty": 0.0,
    "target_margin_pct": 12.0,  # forwarder's typical target margin
}


class PricingAgent(BaseAgent):
    name = "pricing"

    def __init__(self, provider=None, rules: dict | None = None) -> None:
        super().__init__(provider)
        self.rules = {**DEFAULT_RULES, **(rules or {})}

    def estimate(self, offer: dict) -> AgentResult:
        assumptions: list[str] = []
        missing: list[str] = []

        distance = offer.get("distance_km")
        if not distance:
            missing.append("distance_km")
            distance = self._mock_distance(offer)
            assumptions.append(
                f"distance assumed {distance:.0f} km (mock provider; "
                "replace with authorised distance provider)"
            )

        base = self.rules["base_eur_per_km"]
        mult = 1.0
        vt = offer.get("vehicle_type")
        if vt in self.rules["vehicle_multiplier"]:
            mult *= self.rules["vehicle_multiplier"][vt]
            assumptions.append(f"vehicle multiplier for {vt}")
        if offer.get("adr_required"):
            mult *= self.rules["adr_multiplier"]
            assumptions.append("ADR surcharge applied")
        if vt in {"reefer", "frigo"} or offer.get("temperature_c") is not None:
            mult *= self.rules["reefer_multiplier"]
            assumptions.append("refrigerated surcharge applied")

        loaded_km = distance
        deadhead_km = distance * self.rules["deadhead_pct"]
        toll = (loaded_km) * self.rules["toll_per_km"]

        # Carrier buy-price midpoint and a +/-12% range.
        buy_mid = base * mult * (loaded_km + deadhead_km) + toll
        buy_low, buy_high = buy_mid * 0.88, buy_mid * 1.12

        target = self.rules["target_margin_pct"] / 100.0
        sell_mid = buy_mid * (1 + target)
        sell_low, sell_high = sell_mid * 0.95, sell_mid * 1.12

        # If the customer already named a rate, anchor the sell side to it.
        customer_rate = offer.get("customer_rate")
        if customer_rate:
            sell_low = min(sell_low, customer_rate)
            sell_high = max(sell_high, customer_rate)
            assumptions.append("sell range anchored to stated customer rate")

        margin_low = sell_low - buy_high
        margin_high = sell_high - buy_low
        margin_mid = sell_mid - buy_mid
        margin_pct = (margin_mid / sell_mid * 100) if sell_mid else 0.0

        confidence = 0.7 if not missing else 0.45
        warnings = []
        if margin_low < 0:
            warnings.append("downside scenario is loss-making")
        if margin_pct < 6:
            warnings.append("thin margin")

        currency = offer.get("currency", "EUR")
        return self._result(
            summary=(
                f"Estimated margin {margin_pct:.0f}% "
                f"({margin_low:.0f}–{margin_high:.0f} {currency}). "
                "Rule-based estimate, not a live market rate."
            ),
            output={
                "currency": currency,
                "carrier_cost_low": round(buy_low),
                "carrier_cost_high": round(buy_high),
                "sell_low": round(sell_low),
                "sell_high": round(sell_high),
                "margin_low": round(margin_low),
                "margin_high": round(margin_high),
                "margin_pct": round(margin_pct, 1),
                "loaded_km": round(loaded_km),
                "deadhead_km": round(deadhead_km),
                "toll": round(toll),
                "assumptions": assumptions,
                "sensitivity": {
                    "buy_mid": round(buy_mid),
                    "sell_mid": round(sell_mid),
                },
                "recommended_negotiation_range": [round(buy_low), round(buy_mid)],
                "warnings": warnings,
            },
            confidence=confidence,
            missing_fields=missing,
            factors=assumptions,
        )

    @staticmethod
    def _mock_distance(offer: dict) -> float:
        """Fallback distance when no provider/manual value is present.

        Uses a geographic (haversine × road-factor) estimate over a table of
        European freight hubs, so any known lane gets a sensible distance; falls
        back to a conservative 800 km only when a city is unrecognised.
        """
        from ..geo import estimate_distance_km

        est = estimate_distance_km(offer.get("origin_city"), offer.get("dest_city"))
        return float(est) if est else 800.0
