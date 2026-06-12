"""Communication Drafting agent.

Creates editable multilingual (PL/EN/IT/DE) communication drafts for customers
and carriers. NEVER sends. Produces a draft plus an explicit, disabled
"Approve & Send" intent that only an authorised, human-approved integration
could ever act on.
"""

from __future__ import annotations

from .base import AgentResult, BaseAgent

PURPOSES = [
    "offer_still_available",
    "request_missing_details",
    "propose_rate",
    "ask_vehicle_availability",
    "confirm_details",
    "request_status",
    "warn_delay",
    "request_cmr_pod",
    "remind_missing_docs",
    "escalate_problem",
    "summarize_call",
    "handover_note",
]

# Minimal multilingual templates. {field} placeholders are filled from context.
_TEMPLATES = {
    "request_missing_details": {
        "en": "Hello {name},\n\nThank you for the freight {route}. To quote we still "
        "need: {missing}. Could you confirm these?\n\nBest regards",
        "pl": "Dzień dobry {name},\n\nDziękuję za ładunek {route}. Do wyceny brakuje "
        "nam: {missing}. Czy mógłbyś/mogłabyś potwierdzić te dane?\n\nPozdrawiam",
        "it": "Buongiorno {name},\n\nGrazie per il carico {route}. Per quotare ci "
        "servono ancora: {missing}. Può confermare?\n\nCordiali saluti",
        "de": "Guten Tag {name},\n\nvielen Dank für die Ladung {route}. Für ein "
        "Angebot fehlen uns noch: {missing}. Können Sie das bestätigen?\n\nMit freundlichen Grüßen",
    },
    "ask_vehicle_availability": {
        "en": "Hello {name},\n\nDo you have a {vehicle} available for {route} on "
        "{date}? If so, what is your best price?\n\nBest regards",
        "pl": "Dzień dobry {name},\n\nCzy macie dostępny {vehicle} na trasę {route} "
        "dnia {date}? Jeśli tak, jaka jest najlepsza cena?\n\nPozdrawiam",
        "it": "Buongiorno {name},\n\nAvete un {vehicle} disponibile per {route} il "
        "{date}? In caso, qual è il miglior prezzo?\n\nCordiali saluti",
        "de": "Guten Tag {name},\n\nhaben Sie ein {vehicle} für {route} am {date} "
        "verfügbar? Wenn ja, was ist Ihr bester Preis?\n\nMit freundlichen Grüßen",
    },
    "warn_delay": {
        "en": "Hello {name},\n\nWe want to flag a possible delay on shipment {route}. "
        "We are confirming with the carrier and will update you shortly.\n\nBest regards",
        "pl": "Dzień dobry {name},\n\nInformujemy o możliwym opóźnieniu transportu "
        "{route}. Potwierdzamy u przewoźnika i wrócimy z informacją.\n\nPozdrawiam",
        "it": "Buongiorno {name},\n\nSegnaliamo un possibile ritardo sulla spedizione "
        "{route}. Stiamo verificando con il vettore e aggiorneremo a breve.\n\nCordiali saluti",
        "de": "Guten Tag {name},\n\nwir weisen auf eine mögliche Verzögerung bei "
        "Sendung {route} hin. Wir klären mit dem Frachtführer und melden uns.\n\nMit freundlichen Grüßen",
    },
    "request_cmr_pod": {
        "en": "Hello {name},\n\nCould you please send the signed CMR / POD for {route}? "
        "We need it to close the file.\n\nBest regards",
        "pl": "Dzień dobry {name},\n\nProszę o przesłanie podpisanego CMR / POD dla "
        "{route}. Jest nam potrzebny do zamknięcia zlecenia.\n\nPozdrawiam",
        "it": "Buongiorno {name},\n\npotete inviare il CMR / POD firmato per {route}? "
        "Ci serve per chiudere la pratica.\n\nCordiali saluti",
        "de": "Guten Tag {name},\n\nkönnten Sie den unterschriebenen CMR / POD für "
        "{route} senden? Wir brauchen ihn zum Abschluss.\n\nMit freundlichen Grüßen",
    },
}

_GENERIC = {
    "en": "Hello {name},\n\nRegarding {route}: {purpose}.\n\nBest regards",
    "pl": "Dzień dobry {name},\n\nW sprawie {route}: {purpose}.\n\nPozdrawiam",
    "it": "Buongiorno {name},\n\nIn merito a {route}: {purpose}.\n\nCordiali saluti",
    "de": "Guten Tag {name},\n\nbezüglich {route}: {purpose}.\n\nMit freundlichen Grüßen",
}


class CommunicationAgent(BaseAgent):
    name = "communication"

    def draft(
        self,
        *,
        purpose: str,
        language: str = "en",
        recipient: str = "",
        recipient_type: str = "carrier",
        context: dict | None = None,
    ) -> AgentResult:
        context = context or {}
        language = language if language in {"pl", "en", "it", "de"} else "en"
        tmpl = _TEMPLATES.get(purpose, _GENERIC).get(language) or _GENERIC["en"]

        fields = {
            "name": recipient or context.get("name", "—"),
            "route": context.get("route", "—"),
            "missing": ", ".join(context.get("missing", [])) or "—",
            "vehicle": context.get("vehicle", "vehicle"),
            "date": context.get("date", "—"),
            "purpose": purpose.replace("_", " "),
        }
        body = tmpl.format(**fields)

        uncertainties = []
        if "—" in body:
            uncertainties.append("some placeholders are unresolved")
        review = purpose in {"propose_rate", "escalate_problem", "confirm_details"}

        return self._result(
            summary=f"Draft '{purpose}' in {language} prepared (NOT sent).",
            output={
                "recipient_type": recipient_type,
                "recipient": recipient,
                "language": language,
                "purpose": purpose,
                "body": body,
                "uncertainties": uncertainties,
                "review_advisable": review,
                # Disabled until an authorised integration is configured.
                "approve_and_send_enabled": False,
            },
            confidence=0.75 if not uncertainties else 0.6,
            missing_fields=[k for k, v in fields.items() if v == "—"],
            factors=[f"purpose:{purpose}", f"lang:{language}"],
        )
