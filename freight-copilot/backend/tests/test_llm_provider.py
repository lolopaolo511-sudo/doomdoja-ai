"""LLM enrichment tests — wiring + deterministic fallback, no network.

These use a fake provider so we never call out. They prove two invariants:
  1. When an LLM provider is active, agents use its output.
  2. When the LLM fails (returns None), agents fall back to the rule-based path
     and behave exactly as in deterministic mode.
"""

from __future__ import annotations

from app.agents.communication import CommunicationAgent
from app.agents.intake import IntakeAgent
from app.agents.provider import DeterministicProvider, MockProvider


class FakeLLM:
    """Stand-in LLM provider that returns a canned completion (or None)."""

    name = "fake"
    model = "fake-model"
    is_llm = True

    def __init__(self, reply: str | None):
        self.reply = reply
        self.calls = 0

    def complete(self, system: str, user: str, max_tokens: int = 1024):
        self.calls += 1
        return self.reply


def test_deterministic_provider_makes_no_llm_calls():
    p = DeterministicProvider()
    assert p.is_llm is False
    assert p.complete("s", "u") is None
    assert MockProvider().is_llm is False


def test_communication_uses_llm_polish_when_available():
    fake = FakeLLM("Dzień dobry,\n\nczy ładunek Warsaw→Milan jest dostępny?\n\nPozdrawiam")
    agent = CommunicationAgent(provider=fake)
    res = agent.draft(
        purpose="ask_vehicle_availability",
        language="pl",
        recipient="Dispatcher",
        context={"route": "Warsaw→Milan"},
    )
    assert fake.calls == 1
    assert res.output["enriched_by"] == "fake-model"
    assert "Pozdrawiam" in res.output["body"]
    # Enrichment never flips the send guard.
    assert res.output["approve_and_send_enabled"] is False


def test_communication_falls_back_to_template_when_llm_returns_none():
    fake = FakeLLM(None)
    agent = CommunicationAgent(provider=fake)
    res = agent.draft(
        purpose="ask_vehicle_availability",
        language="en",
        recipient="X",
        context={"route": "A→B", "vehicle": "reefer", "date": "12/06"},
    )
    assert fake.calls == 1
    assert res.output["enriched_by"] is None
    assert res.output["body"]  # deterministic template still produced a draft


def test_intake_llm_fills_missing_fields_only():
    # Regex won't find a route in this vague text; the LLM supplies it.
    fake = FakeLLM(
        '{"origin_city": "Gdansk", "origin_country": "PL", "dest_city": "Lyon", '
        '"dest_country": "FR", "weight_kg": 19000, "vehicle_type": "tautliner", '
        '"adr_required": false, "customer_rate": 1700, "currency": "EUR", "language": "en"}'
    )
    res = IntakeAgent(provider=fake).parse("we have a load, details by phone", "manual")
    data = res.output["data"]
    assert data["origin_city"] == "Gdansk"
    assert data["dest_city"] == "Lyon"
    assert data["weight_kg"] == 19000
    assert data.get("_llm_assisted") is True


def test_intake_llm_does_not_override_regex_values():
    # Regex already extracts Warsaw/Milan; a contradictory LLM reply must NOT win.
    fake = FakeLLM('{"origin_city": "WRONG", "dest_city": "WRONG"}')
    text = "Carico Warsaw (PL) -> Milan (IT), 22t tautliner, 1850 EUR"
    res = IntakeAgent(provider=fake).parse(text, "manual")
    data = res.output["data"]
    assert data["origin_city"] == "Warsaw"
    assert data["dest_city"] == "Milan"


def test_intake_llm_bad_json_is_ignored():
    res = IntakeAgent(provider=FakeLLM("not json at all")).parse(
        "Carico Warsaw (PL) -> Milan (IT), 22t", "manual"
    )
    assert res.output["data"]["origin_city"] == "Warsaw"  # deterministic path intact
