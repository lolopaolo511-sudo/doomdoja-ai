"""Intake & Inbox Dispatcher agent.

Converts incoming freight opportunities (pasted text, form, CSV row, mock
email) into structured records. Deterministic, multilingual-aware extraction
with explicit missing-field and confidence reporting. All raw text is first
passed through the SafetySupervisor and is treated as untrusted data.
"""

from __future__ import annotations

import re

from .base import AgentResult, BaseAgent
from .safety_supervisor import SafetySupervisorAgent

# Required fields for an offer to be considered complete enough to score.
CRITICAL_FIELDS = [
    "origin_city",
    "dest_city",
    "pickup_date",
    "weight_kg",
    "vehicle_type",
]

_LANG_HINTS = {
    "pl": ["ładunek", "waga", "załadunek", "rozładunek", "paleta", "trasa", "data"],
    "it": ["carico", "peso", "carico", "consegna", "bancali", "ritiro"],
    "de": ["ladung", "gewicht", "beladung", "lieferung", "paletten", "abholung"],
    "en": ["cargo", "weight", "loading", "delivery", "pallets", "pickup"],
}

_VEHICLE_WORDS = {
    "reefer": ["reefer", "chłodnia", "frigo", "kühl", "refriger"],
    "tautliner": ["tautliner", "plandeka", "centina", "plane", "curtain"],
    "box": ["box", "kontener", "furgone", "koffer"],
    "mega": ["mega"],
    "frigo": ["frigo"],
}

_CITY_COUNTRY = re.compile(r"(?P<city>[A-ZÀ-Ž][A-Za-zÀ-ž.\-]{1,29})\s*\((?P<cc>[A-Z]{2})\)")
_WEIGHT = re.compile(r"(?P<val>\d{1,3}(?:[.,]\d{1,3})?)\s*(?:t|tony|tonnes|tonn?e|kg)", re.I)
_PALLETS = re.compile(r"(?P<val>\d{1,2})\s*(?:pallet|palet|bancali|paletten|epal|eur-?pal)", re.I)
_LDM = re.compile(r"(?P<val>\d{1,2}(?:[.,]\d)?)\s*(?:ldm|m\s* load|metr)", re.I)
_RATE = re.compile(r"(?P<val>\d{3,5})\s*(?P<cur>eur|€|pln|zł)", re.I)
_DATE = re.compile(r"(?P<d>\d{1,2})[./-](?P<m>\d{1,2})(?:[./-](?P<y>\d{2,4}))?")
_ADR = re.compile(r"(?i)\badr\b")


class IntakeAgent(BaseAgent):
    name = "intake"

    def __init__(self, provider=None) -> None:
        super().__init__(provider)
        self.safety = SafetySupervisorAgent(self.provider)

    def detect_language(self, text: str) -> str:
        low = text.lower()
        scores = {lang: sum(low.count(w) for w in words) for lang, words in _LANG_HINTS.items()}
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "en"

    def parse(self, text: str, source_platform: str = "manual") -> AgentResult:
        safety = self.safety.scan_text(text)
        data: dict = {"source_platform": source_platform, "raw_text": text}

        # Route: look for "City (CC)" occurrences, first = origin, second = dest.
        locations = _CITY_COUNTRY.findall(text)
        if locations:
            data["origin_city"] = locations[0][0].strip()
            data["origin_country"] = locations[0][1]
        if len(locations) > 1:
            data["dest_city"] = locations[1][0].strip()
            data["dest_country"] = locations[1][1]

        # Weight (normalise tonnes → kg)
        wm = _WEIGHT.search(text)
        if wm:
            val = float(wm.group("val").replace(",", "."))
            unit = wm.group(0).lower()
            data["weight_kg"] = val * 1000 if ("t" in unit and "kg" not in unit) else val

        pm = _PALLETS.search(text)
        if pm:
            data["pallets"] = int(pm.group("val"))

        lm = _LDM.search(text)
        if lm:
            data["loading_meters"] = float(lm.group("val").replace(",", "."))

        rm = _RATE.search(text)
        if rm:
            data["customer_rate"] = float(rm.group("val"))
            cur = rm.group("cur").lower()
            data["currency"] = "PLN" if cur in {"pln", "zł"} else "EUR"

        dm = _DATE.search(text)
        if dm:
            data["pickup_date_raw"] = dm.group(0)

        if _ADR.search(text):
            data["adr_required"] = True

        for vtype, words in _VEHICLE_WORDS.items():
            if any(w in text.lower() for w in words):
                data["vehicle_type"] = vtype
                if vtype in {"reefer", "frigo"}:
                    data["reefer"] = True
                break

        data["language"] = self.detect_language(text)

        missing = [f for f in CRITICAL_FIELDS if not data.get(f) and f != "pickup_date"]
        if "pickup_date_raw" not in data:
            missing.append("pickup_date")

        # Confidence scales with how many critical fields were extracted.
        present = len(CRITICAL_FIELDS) - len(missing)
        confidence = round(0.4 + 0.5 * (present / len(CRITICAL_FIELDS)), 2)

        triage = "needs_review" if missing else "ready_for_scoring"
        if safety.output.get("severity") == "high":
            triage = "needs_review"

        summary = (
            f"Extracted {present}/{len(CRITICAL_FIELDS)} critical fields "
            f"(lang={data['language']}). "
            + ("Missing: " + ", ".join(missing) if missing else "No critical gaps.")
        )

        return self._result(
            summary=summary,
            output={
                "data": data,
                "missing_fields": missing,
                "triage_state": triage,
                "safety": safety.output,
            },
            confidence=confidence,
            missing_fields=missing,
            factors=[f"source:{source_platform}", f"lang:{data['language']}"],
        )

    @staticmethod
    def is_duplicate(new: dict, existing: list[dict]) -> str | None:
        """Naive duplicate detection on route + pickup + weight."""
        key = (
            (new.get("origin_city") or "").lower(),
            (new.get("dest_city") or "").lower(),
            new.get("pickup_date_raw"),
            new.get("weight_kg"),
        )
        for ex in existing:
            ek = (
                (ex.get("origin_city") or "").lower(),
                (ex.get("dest_city") or "").lower(),
                ex.get("pickup_date_raw"),
                ex.get("weight_kg"),
            )
            if key == ek and any(key):
                return ex.get("id")
        return None
