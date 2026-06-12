"""JSON API routes. Read endpoints + the safe, human-gated actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import services
from ..config import get_settings
from ..db import get_session

router = APIRouter(prefix="/api", tags=["api"])


class IntakeIn(BaseModel):
    text: str
    source: str = "manual"


class NoteIn(BaseModel):
    title: str
    body: str
    tags: list[str] = []
    provenance: str = "user_entered"


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/flags")
def flags() -> dict:
    return get_settings().feature_flags()


@router.post("/intake")
def intake(payload: IntakeIn, session: Session = Depends(get_session)) -> dict:
    offer = services.intake_offer(session, payload.text, payload.source)
    return {
        "id": offer.id,
        "score": offer.score,
        "priority": offer.priority,
        "missing_fields": offer.missing_fields,
        "triage_state": offer.triage_state,
    }


@router.get("/offers")
def list_offers(session: Session = Depends(get_session)) -> list[dict]:
    offers = session.scalars(
        select(m.FreightOffer)
        .where(m.FreightOffer.is_deleted == False)  # noqa: E712
        .order_by(m.FreightOffer.score.desc().nullslast())
    ).all()
    return [
        {
            "id": o.id,
            "route": f"{o.origin_city}→{o.dest_city}",
            "score": o.score,
            "priority": o.priority,
            "triage_state": o.triage_state,
            "source": o.source_platform,
            "rate": o.customer_rate,
            "currency": o.currency,
            "missing": o.missing_fields,
        }
        for o in offers
    ]


@router.get("/offers/{offer_id}")
def offer_detail(offer_id: str, session: Session = Depends(get_session)) -> dict:
    offer = session.get(m.FreightOffer, offer_id)
    if not offer:
        raise HTTPException(404, "offer not found")
    analysis = services.analyze_offer(session, offer)
    session.commit()
    matches = services.match_carriers(session, offer)
    return {
        "id": offer.id,
        "raw_text": offer.raw_text,
        "route": f"{offer.origin_city}→{offer.dest_city}",
        "score": offer.score,
        "priority": offer.priority,
        "missing_fields": offer.missing_fields,
        "analysis": analysis,
        "carriers": matches,
    }


@router.get("/carriers")
def list_carriers(session: Session = Depends(get_session)) -> list[dict]:
    carriers = session.scalars(select(m.Carrier).where(m.Carrier.is_deleted == False)).all()  # noqa: E712
    return [
        {
            "id": c.id,
            "name": c.legal_name,
            "country": c.country,
            "risk": c.risk_level,
            "lanes": c.routes_served,
            "vehicles": c.vehicle_types,
            "reliability": c.reliability_rating,
        }
        for c in carriers
    ]


@router.get("/shipments")
def list_shipments(session: Session = Depends(get_session)) -> list[dict]:
    ships = session.scalars(select(m.Shipment)).all()
    out = []
    for s in ships:
        ev = services.evaluate_shipment(session, s)
        out.append(
            {
                "id": s.id,
                "reference": s.reference,
                "state": s.state,
                "route": f"{s.origin} → {s.destination}",
                "alerts": ev["monitoring"]["output"]["alerts"],
                "documents": ev["documents"]["output"],
            }
        )
    return out


@router.get("/approvals")
def list_approvals(session: Session = Depends(get_session)) -> list[dict]:
    aps = session.scalars(select(m.ApprovalRequest)).all()
    return [
        {
            "id": a.id,
            "action": a.action,
            "system": a.external_system,
            "payload": a.payload,
            "risks": a.risks,
            "state": a.state,
            "reasoning": a.reasoning_summary,
        }
        for a in aps
    ]


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: str, decision: str, session: Session = Depends(get_session)) -> dict:
    ap = session.get(m.ApprovalRequest, approval_id)
    if not ap:
        raise HTTPException(404, "approval not found")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")
    ap = services.decide_approval(session, ap, decision=decision)
    return {"id": ap.id, "state": ap.state, "result_note": ap.result_note}


@router.get("/knowledge")
def list_notes(q: str = "", session: Session = Depends(get_session)) -> list[dict]:
    notes = session.scalars(select(m.KnowledgeNote)).all()
    data = [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "tags": n.tags,
            "provenance": n.provenance,
            "approved": n.approved,
        }
        for n in notes
    ]
    if q:
        ql = q.lower()
        data = [n for n in data if ql in (n["title"] + n["body"] + " ".join(n["tags"])).lower()]
    return data


@router.post("/knowledge")
def add_note(payload: NoteIn, session: Session = Depends(get_session)) -> dict:
    note = m.KnowledgeNote(
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        provenance=payload.provenance,
        approved=True,
    )
    session.add(note)
    session.commit()
    return {"id": note.id}


@router.delete("/knowledge/{note_id}")
def delete_note(note_id: str, session: Session = Depends(get_session)) -> dict:
    note = session.get(m.KnowledgeNote, note_id)
    if not note:
        raise HTTPException(404, "note not found")
    session.delete(note)
    session.commit()
    return {"deleted": note_id}


@router.get("/integrations")
def integrations(session: Session = Depends(get_session)) -> list[dict]:
    cfgs = session.scalars(select(m.IntegrationConfig)).all()
    return [
        {
            "name": c.name,
            "enabled": c.enabled,
            "read": c.read_enabled,
            "write": c.write_enabled,
            "mock": c.mock_enabled,
            "credential_status": c.credential_status,
        }
        for c in cfgs
    ]
