"""Service layer tying agents to persisted entities.

Centralises the orchestration each workflow needs so both the JSON API and the
server-rendered views share identical logic. Every agent run is recorded as an
AgentRun + AgentRecommendation for traceability.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from . import models as m
from .agents import (
    CarrierMatchingAgent,
    CarrierRiskAgent,
    IntakeAgent,
    MonitoringAgent,
    PricingAgent,
    SafetySupervisorAgent,
    ScoutAgent,
)
from .agents.document_controller import DocumentControllerAgent


def _offer_dict(o: m.FreightOffer) -> dict:
    return {
        "id": o.id,
        "origin_city": o.origin_city,
        "origin_country": o.origin_country,
        "dest_city": o.dest_city,
        "dest_country": o.dest_country,
        "weight_kg": o.weight_kg,
        "vehicle_type": o.vehicle_type,
        "adr_required": o.adr_required,
        "temperature_c": o.temperature_c,
        "pickup_date": o.pickup_date,
        "customer_rate": o.customer_rate,
        "currency": o.currency,
        "distance_km": o.distance_km,
        "unloading_method": o.unloading_method,
    }


def _carrier_dict(c: m.Carrier) -> dict:
    return {
        "id": c.id,
        "legal_name": c.legal_name,
        "vat_number": c.vat_number,
        "routes_served": c.routes_served,
        "preferred_lanes": c.preferred_lanes,
        "blacklisted_lanes": c.blacklisted_lanes,
        "vehicle_types": c.vehicle_types,
        "adr_capable": c.adr_capable,
        "reefer_capable": c.reefer_capable,
        "reliability_rating": c.reliability_rating,
        "completed_transports": c.completed_transports,
        "risk_level": c.risk_level,
        "last_cooperation_date": c.last_cooperation_date,
        "verification_source": c.verification_source,
    }


def _record_run(session: Session, result, entity_type: str, entity_id: str) -> None:
    run = m.AgentRun(
        agent=result.agent,
        entity_type=entity_type,
        entity_id=entity_id,
        provider=result.provider,
        model=result.model,
        confidence=result.confidence,
        missing_fields=result.missing_fields,
    )
    session.add(run)
    session.flush()
    session.add(
        m.AgentRecommendation(
            agent_run_id=run.id,
            agent=result.agent,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=result.summary,
            output=result.output,
            confidence=result.confidence,
        )
    )


def intake_offer(session: Session, text: str, source: str = "manual") -> m.FreightOffer:
    """Workflow A entry: parse pasted text into a stored, scored offer."""
    intake = IntakeAgent()
    res = intake.parse(text, source_platform=source)
    data = res.output["data"]
    offer = m.FreightOffer(
        source_platform=data.get("source_platform", source),
        raw_text=text,
        language=data.get("language", "en"),
        origin_city=data.get("origin_city"),
        origin_country=data.get("origin_country"),
        dest_city=data.get("dest_city"),
        dest_country=data.get("dest_country"),
        weight_kg=data.get("weight_kg"),
        pallets=data.get("pallets"),
        vehicle_type=data.get("vehicle_type"),
        adr_required=data.get("adr_required", False),
        currency=data.get("currency", "EUR"),
        customer_rate=data.get("customer_rate"),
        missing_fields=res.missing_fields,
        intake_confidence=res.confidence,
        triage_state=res.output["triage_state"],
    )
    session.add(offer)
    session.flush()
    _record_run(session, res, "freight_offer", offer.id)
    audit.record(
        session,
        action="intake_offer",
        actor="forwarder",
        entity_type="freight_offer",
        entity_id=offer.id,
        detail={"source": source, "safety": res.output.get("safety")},
    )
    # Immediately score it.
    analyze_offer(session, offer)
    session.commit()
    return offer


def analyze_offer(session: Session, offer: m.FreightOffer) -> dict:
    """Run pricing + scoring and persist score/priority + a RateEstimate."""
    od = _offer_dict(offer)
    pricing = PricingAgent().estimate(od)
    scout = ScoutAgent().score(od, margin_pct=pricing.output.get("margin_pct"))

    offer.score = scout.output["score"]
    offer.priority = scout.output["priority"]

    # Replace any prior estimate
    existing = session.scalars(
        select(m.RateEstimate).where(m.RateEstimate.offer_id == offer.id)
    ).all()
    for e in existing:
        session.delete(e)
    po = pricing.output
    session.add(
        m.RateEstimate(
            offer_id=offer.id,
            carrier_cost_low=po["carrier_cost_low"],
            carrier_cost_high=po["carrier_cost_high"],
            sell_low=po["sell_low"],
            sell_high=po["sell_high"],
            margin_low=po["margin_low"],
            margin_high=po["margin_high"],
            margin_pct=po["margin_pct"],
            currency=po["currency"],
            assumptions=po["assumptions"],
            confidence=pricing.confidence,
        )
    )
    _record_run(session, pricing, "freight_offer", offer.id)
    _record_run(session, scout, "freight_offer", offer.id)
    session.flush()
    return {"pricing": pricing.to_dict(), "scout": scout.to_dict()}


def match_carriers(session: Session, offer: m.FreightOffer) -> dict:
    """Workflow B: rank carriers and run risk assessment on the top ones."""
    carriers = session.scalars(select(m.Carrier).where(m.Carrier.is_deleted == False)).all()  # noqa: E712
    matcher = CarrierMatchingAgent()
    res = matcher.shortlist(_offer_dict(offer), [_carrier_dict(c) for c in carriers])
    _record_run(session, res, "freight_offer", offer.id)

    # Risk-assess each shortlisted carrier (so expired insurance gets flagged).
    risk = CarrierRiskAgent()
    by_id = {c.id: c for c in carriers}
    enriched = []
    for entry in res.output["shortlist"]:
        c = by_id.get(entry["carrier_id"])
        if not c:
            continue
        docs = [{"doc_type": d.doc_type, "expiry_date": d.expiry_date} for d in c.documents]
        flags = [{"flag": f.flag, "severity": f.severity} for f in c.risk_flags]
        ra = risk.assess(_carrier_dict(c), docs, flags)
        entry["risk_assessment"] = ra.output
        enriched.append(entry)
    res.output["shortlist"] = enriched
    session.commit()
    return res.to_dict()


def evaluate_shipment(session: Session, shipment: m.Shipment) -> dict:
    """Workflow C: monitoring + document completeness for a shipment."""
    milestones = [
        {"name": ms.name, "occurred_at": ms.occurred_at, "expected_at": ms.expected_at}
        for ms in shipment.milestones
    ]
    mon = MonitoringAgent().evaluate(
        {"state": shipment.state, "origin": shipment.origin, "destination": shipment.destination},
        milestones,
    )
    docs = session.scalars(select(m.Document).where(m.Document.shipment_id == shipment.id)).all()
    doc_check = DocumentControllerAgent().check(
        {"state": shipment.state},
        [
            {
                "doc_type": d.doc_type,
                "status": d.status,
                "expiry_date": d.expiry_date,
                "readable": d.readable,
                "signatures_present": d.signatures_present,
                "missing_pages": d.missing_pages,
            }
            for d in docs
        ],
    )
    _record_run(session, mon, "shipment", shipment.id)
    _record_run(session, doc_check, "shipment", shipment.id)
    session.commit()
    return {"monitoring": mon.to_dict(), "documents": doc_check.to_dict()}


def decide_approval(
    session: Session, approval: m.ApprovalRequest, *, decision: str, actor: str = "forwarder"
) -> m.ApprovalRequest:
    """Approve/reject. In demo mode an approval is SIMULATED, never a real write."""
    from .config import get_settings

    settings = get_settings()
    supervisor = SafetySupervisorAgent()

    if decision == "approved":
        guard = supervisor.guard_external_action(approved=True, system=approval.external_system)
        if settings.demo_mode or not settings.external_writes_enabled:
            approval.state = "simulated"
            approval.result_note = "DEMO/dry-run: action simulated, no external write performed."
        else:  # pragma: no cover - real writes are out of scope for the MVP
            approval.state = "approved"
            approval.result_note = "Approved; adapter would perform the write."
        _ = guard
    else:
        approval.state = "rejected"
        approval.result_note = "Rejected by operator."

    approval.decided_by = actor
    approval.decided_at = datetime.now(UTC)
    audit.record(
        session,
        action=f"approval_{approval.state}",
        actor=actor,
        entity_type="approval_request",
        entity_id=approval.id,
        detail={"action": approval.action, "system": approval.external_system},
    )
    session.commit()
    return approval
