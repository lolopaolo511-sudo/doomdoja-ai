"""Server-rendered dashboard (Jinja2 + Tailwind via CDN).

This is the MVP UI: it renders directly from the backend so the whole app runs
with one command and zero front-end build. The production target is a Next.js
front-end consuming the JSON API (see docs/ROADMAP.md).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from .. import services
from ..config import get_settings
from ..db import get_session

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def render(request: Request, name: str, **kw):
    """Render a template using the modern Starlette (request, name, context) API."""
    ctx = {"app_name": get_settings().app_name}
    ctx.update(kw)
    return templates.TemplateResponse(request, name, ctx)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    offers = session.scalars(
        select(m.FreightOffer).where(m.FreightOffer.is_deleted == False)  # noqa: E712
    ).all()
    shipments = session.scalars(select(m.Shipment)).all()
    alerts = session.scalars(select(m.Alert).where(m.Alert.resolved == False)).all()  # noqa: E712
    approvals = session.scalars(
        select(m.ApprovalRequest).where(m.ApprovalRequest.state == "pending")
    ).all()
    high = [o for o in offers if (o.score or 0) >= 60]
    urgent = [o for o in offers if o.triage_state == "needs_review"]
    delayed = [s for s in shipments if s.state == "problem"]
    return render(
        request,
        "dashboard.html",
        metrics={
            "new_offers": len(offers),
            "urgent": len(urgent),
            "high": len(high),
            "active": len(shipments),
            "delayed": len(delayed),
            "alerts": len(alerts),
            "approvals": len(approvals),
        },
        high=high[:6],
        alerts=alerts,
        flags=get_settings().feature_flags(),
    )


@router.get("/opportunities", response_class=HTMLResponse)
def opportunities(request: Request, session: Session = Depends(get_session)):
    offers = session.scalars(
        select(m.FreightOffer)
        .where(m.FreightOffer.is_deleted == False)  # noqa: E712
        .order_by(m.FreightOffer.score.desc().nullslast())
    ).all()
    return render(request, "opportunities.html", offers=offers)


@router.post("/opportunities/intake")
def intake_form(text: str = Form(...), session: Session = Depends(get_session)):
    if text.strip():
        offer = services.intake_offer(session, text.strip(), source="manual")
        return RedirectResponse(f"/opportunities/{offer.id}", status_code=303)
    return RedirectResponse("/opportunities", status_code=303)


@router.get("/opportunities/{offer_id}", response_class=HTMLResponse)
def freight_detail(offer_id: str, request: Request, session: Session = Depends(get_session)):
    offer = session.get(m.FreightOffer, offer_id)
    if not offer:
        return RedirectResponse("/opportunities", status_code=303)
    analysis = services.analyze_offer(session, offer)
    session.commit()
    matches = services.match_carriers(session, offer)
    estimate = session.scalars(
        select(m.RateEstimate).where(m.RateEstimate.offer_id == offer.id)
    ).first()
    return render(
        request,
        "freight_detail.html",
        offer=offer,
        analysis=analysis,
        matches=matches,
        estimate=estimate,
    )


@router.get("/carriers", response_class=HTMLResponse)
def carriers(request: Request, session: Session = Depends(get_session)):
    rows = session.scalars(select(m.Carrier).where(m.Carrier.is_deleted == False)).all()  # noqa: E712
    return render(request, "carriers.html", carriers=rows)


@router.get("/transports", response_class=HTMLResponse)
def transports(request: Request, session: Session = Depends(get_session)):
    ships = session.scalars(select(m.Shipment)).all()
    data = []
    for s in ships:
        ev = services.evaluate_shipment(session, s)
        data.append({"s": s, "mon": ev["monitoring"]["output"], "docs": ev["documents"]["output"]})
    return render(request, "transports.html", transports=data)


@router.get("/approvals", response_class=HTMLResponse)
def approvals(request: Request, session: Session = Depends(get_session)):
    aps = session.scalars(select(m.ApprovalRequest).order_by(m.ApprovalRequest.created_at)).all()
    return render(request, "approvals.html", approvals=aps, demo=get_settings().demo_mode)


@router.post("/approvals/{approval_id}")
def approval_decide(
    approval_id: str, decision: str = Form(...), session: Session = Depends(get_session)
):
    ap = session.get(m.ApprovalRequest, approval_id)
    if ap and decision in {"approved", "rejected"}:
        services.decide_approval(session, ap, decision=decision)
    return RedirectResponse("/approvals", status_code=303)


@router.get("/documents", response_class=HTMLResponse)
def documents(request: Request, session: Session = Depends(get_session)):
    docs = session.scalars(select(m.Document)).all()
    return render(request, "documents.html", documents=docs)


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge(request: Request, q: str = "", session: Session = Depends(get_session)):
    notes = session.scalars(select(m.KnowledgeNote).order_by(m.KnowledgeNote.created_at)).all()
    if q:
        ql = q.lower()
        notes = [n for n in notes if ql in (n.title + n.body + " ".join(n.tags)).lower()]
    return render(request, "knowledge.html", notes=notes, q=q)


@router.post("/knowledge/add")
def knowledge_add(
    title: str = Form(...), body: str = Form(...), session: Session = Depends(get_session)
):
    if title.strip() and body.strip():
        session.add(
            m.KnowledgeNote(
                title=title.strip(), body=body.strip(), provenance="user_entered", approved=True
            )
        )
        session.commit()
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/{note_id}/approve")
def knowledge_approve(note_id: str, session: Session = Depends(get_session)):
    n = session.get(m.KnowledgeNote, note_id)
    if n:
        n.approved = True
        n.provenance = "user_entered"
        session.commit()
    return RedirectResponse("/knowledge", status_code=303)


@router.post("/knowledge/{note_id}/delete")
def knowledge_delete(note_id: str, session: Session = Depends(get_session)):
    n = session.get(m.KnowledgeNote, note_id)
    if n:
        session.delete(n)
        session.commit()
    return RedirectResponse("/knowledge", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)):
    integrations = session.scalars(select(m.IntegrationConfig)).all()
    s = get_settings()
    return render(
        request,
        "settings.html",
        flags=s.feature_flags(),
        integrations=integrations,
        timezone=s.timezone,
        currency=s.default_currency,
        language=s.default_language,
        provider=s.llm_provider,
    )
