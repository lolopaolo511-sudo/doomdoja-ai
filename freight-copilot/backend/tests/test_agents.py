"""Unit tests for the operational agents (deterministic behaviour)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.agents import (
    CarrierMatchingAgent,
    CarrierRiskAgent,
    IntakeAgent,
    MonitoringAgent,
    PricingAgent,
    ScoutAgent,
)
from app.agents.communication import CommunicationAgent
from app.agents.document_controller import DocumentControllerAgent


def test_intake_extracts_route_weight_rate_and_language():
    text = "Carico Warsaw (PL) -> Milan (IT), 22t tautliner, ADR, ritiro 12/06, 1850 EUR"
    res = IntakeAgent().parse(text, source_platform="timocom")
    data = res.output["data"]
    assert data["origin_city"] == "Warsaw" and data["origin_country"] == "PL"
    assert data["dest_city"] == "Milan" and data["dest_country"] == "IT"
    assert data["weight_kg"] == 22000
    assert data["customer_rate"] == 1850
    assert data["adr_required"] is True
    assert data["language"] == "it"
    assert 0 < res.confidence <= 1


def test_intake_flags_missing_fields():
    res = IntakeAgent().parse("Some vague freight from Berlin to Rome", "manual")
    assert res.missing_fields  # weight/vehicle/etc. missing
    assert res.output["triage_state"] == "needs_review"


def test_scout_scores_and_prioritizes():
    offer = {
        "origin_city": "Warsaw",
        "origin_country": "PL",
        "dest_city": "Milan",
        "dest_country": "IT",
        "pickup_date": None,
        "weight_kg": 22000,
        "vehicle_type": "tautliner",
    }
    res = ScoutAgent().score(offer, margin_pct=15)
    assert 0 <= res.output["score"] <= 100
    assert res.output["priority"] in (
        "contact_now",
        "review_soon",
        "watch",
        "low_priority",
        "reject_candidate",
    )


def test_pricing_is_labelled_estimate_not_market_rate():
    offer = {
        "origin_city": "Warsaw",
        "dest_city": "Milan",
        "vehicle_type": "tautliner",
        "currency": "EUR",
    }
    res = PricingAgent().estimate(offer)
    assert "not a live market rate" in res.summary.lower()
    assert res.output["margin_low"] is not None
    assert res.output["recommended_negotiation_range"]


def test_carrier_matching_excludes_blocked_and_requires_verification():
    offer = {"origin_country": "DE", "dest_country": "IT", "vehicle_type": "box"}
    carriers = [
        {
            "id": "1",
            "legal_name": "Blocked Co",
            "risk_level": "blocked",
            "routes_served": ["DE-IT"],
            "vehicle_types": ["box"],
            "blacklisted_lanes": ["DE-IT"],
        },
        {
            "id": "2",
            "legal_name": "Good Co",
            "risk_level": "low",
            "routes_served": ["DE-IT"],
            "vehicle_types": ["box"],
            "reliability_rating": 5,
            "completed_transports": 10,
        },
    ]
    res = CarrierMatchingAgent().shortlist(offer, carriers)
    assert res.output["human_verification_required"] is True
    top = res.output["shortlist"][0]
    assert top["legal_name"] == "Good Co"  # blocked one is not first


def test_carrier_risk_never_safe_on_single_field_and_flags_expired_insurance():
    carrier = {"legal_name": "X", "vat_number": "PL1", "last_cooperation_date": None}
    docs = [{"doc_type": "insurance", "expiry_date": datetime.now(UTC) - timedelta(days=2)}]
    res = CarrierRiskAgent().assess(carrier, docs, [])
    assert res.output["risk_level"] in ("medium", "high", "blocked")
    assert any("expired" in f for f in res.output["findings"])
    assert res.output["reviewer_required"] is True


def test_monitoring_detects_pickup_delay():
    past = datetime.now(UTC) - timedelta(hours=5)
    milestones = [
        {"name": "transport_created", "occurred_at": past, "expected_at": None},
        {"name": "carrier_assigned", "occurred_at": past, "expected_at": None},
        {"name": "pickup_scheduled", "occurred_at": past, "expected_at": None},
    ]
    res = MonitoringAgent().evaluate({"state": "in_transit"}, milestones)
    kinds = {a["kind"] for a in res.output["alerts"]}
    assert "pickup_delay" in kinds


def test_document_controller_reports_missing_and_is_operational_only():
    res = DocumentControllerAgent().check(
        {"state": "delivered"},
        [{"doc_type": "transport_order", "status": "present"}],
    )
    assert "pod" in res.output["missing"] and "cmr" in res.output["missing"]
    assert "operational check only" in res.summary.lower()


def test_communication_never_sends_and_is_multilingual():
    for lang in ("pl", "en", "it", "de"):
        res = CommunicationAgent().draft(
            purpose="request_missing_details",
            language=lang,
            recipient="X",
            context={"route": "A→B", "missing": ["weight"]},
        )
        assert res.output["approve_and_send_enabled"] is False
        assert res.output["language"] == lang
        assert res.output["body"]
