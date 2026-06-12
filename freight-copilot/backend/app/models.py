"""Relational domain model for Freight Copilot.

Pragmatic modular monolith schema. Uses string UUID primary keys, created/
updated timestamps, source attribution and soft-deletion where useful so the
system stays auditable. SQLite-compatible (JSON columns, string enums).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Enums (kept as plain string constants for SQLite friendliness)
# --------------------------------------------------------------------------- #
TRIAGE_STATES = ("new", "needs_review", "ready_for_scoring", "duplicate", "archived")
PRIORITIES = ("contact_now", "review_soon", "watch", "low_priority", "reject_candidate")
RISK_LEVELS = ("unknown", "low", "medium", "high", "blocked")
SHIPMENT_STATES = (
    "created",
    "carrier_assigned",
    "in_transit",
    "delivered",
    "closed",
    "problem",
)
APPROVAL_STATES = ("pending", "approved", "rejected", "edited", "simulated")
LANGUAGES = ("pl", "en", "it", "de")
NOTE_PROVENANCE = ("confirmed", "observed", "user_entered", "model_suggested", "disputed")


class TimestampMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- #
# Organisation / users / parties
# --------------------------------------------------------------------------- #
class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50), default="forwarder")
    language: Mapped[str] = mapped_column(String(2), default="en")


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(2), default="en")
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# --------------------------------------------------------------------------- #
# Carriers
# --------------------------------------------------------------------------- #
class Carrier(TimestampMixin, Base):
    __tablename__ = "carriers"
    legal_name: Mapped[str] = mapped_column(String(200))
    vat_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    routes_served: Mapped[list] = mapped_column(JSON, default=list)  # ["PL-IT", ...]
    vehicle_types: Mapped[list] = mapped_column(JSON, default=list)
    adr_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    reefer_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_lanes: Mapped[list] = mapped_column(JSON, default=list)
    blacklisted_lanes: Mapped[list] = mapped_column(JSON, default=list)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reliability_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_tendency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_transports: Mapped[int] = mapped_column(Integer, default=0)
    last_cooperation_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), default="unknown")
    verification_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verification_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contacts: Mapped[list[CarrierContact]] = relationship(
        back_populates="carrier", cascade="all, delete-orphan"
    )
    documents: Mapped[list[CarrierDocument]] = relationship(
        back_populates="carrier", cascade="all, delete-orphan"
    )
    risk_flags: Mapped[list[CarrierRiskFlag]] = relationship(
        back_populates="carrier", cascade="all, delete-orphan"
    )


class CarrierContact(TimestampMixin, Base):
    __tablename__ = "carrier_contacts"
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"))
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(2), default="en")
    carrier: Mapped[Carrier] = relationship(back_populates="contacts")


class CarrierDocument(TimestampMixin, Base):
    __tablename__ = "carrier_documents"
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"))
    doc_type: Mapped[str] = mapped_column(String(40))  # license, insurance, ocp...
    status: Mapped[str] = mapped_column(String(20), default="present")
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    carrier: Mapped[Carrier] = relationship(back_populates="documents")


class CarrierRiskFlag(TimestampMixin, Base):
    __tablename__ = "carrier_risk_flags"
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"))
    flag: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    carrier: Mapped[Carrier] = relationship(back_populates="risk_flags")


# --------------------------------------------------------------------------- #
# Freight opportunities
# --------------------------------------------------------------------------- #
class FreightOffer(TimestampMixin, Base):
    __tablename__ = "freight_offers"
    # Source attribution
    source_platform: Mapped[str] = mapped_column(String(40), default="manual")
    source_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(2), default="en")

    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Route (embedded for MVP; normalised Route/Location is a roadmap item)
    origin_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    origin_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    dest_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    dest_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    pickup_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pickup_window: Mapped[str | None] = mapped_column(String(60), nullable=True)
    delivery_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_window: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Cargo / vehicle
    cargo_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    pallets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loading_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    adr_required: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    loading_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    unloading_method: Mapped[str | None] = mapped_column(String(60), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    customer_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_term_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Agent-derived
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    intake_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    triage_state: Mapped[str] = mapped_column(String(30), default="new")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(30), nullable=True)
    duplicate_of: Mapped[str | None] = mapped_column(String(36), nullable=True)


class RateEstimate(TimestampMixin, Base):
    __tablename__ = "rate_estimates"
    offer_id: Mapped[str] = mapped_column(ForeignKey("freight_offers.id"))
    carrier_cost_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    carrier_cost_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    assumptions: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class PricingRule(TimestampMixin, Base):
    __tablename__ = "pricing_rules"
    name: Mapped[str] = mapped_column(String(120))
    lane: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "PL-IT"
    base_eur_per_km: Mapped[float] = mapped_column(Float, default=1.2)
    vehicle_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    urgency_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    adr_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    reefer_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    toll_adjustment: Mapped[float] = mapped_column(Float, default=0.0)
    deadhead_adjustment: Mapped[float] = mapped_column(Float, default=0.10)
    weekend_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CarrierMatch(TimestampMixin, Base):
    __tablename__ = "carrier_matches"
    offer_id: Mapped[str] = mapped_column(ForeignKey("freight_offers.id"))
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"))
    score: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    disqualifiers: Mapped[list] = mapped_column(JSON, default=list)


class CommunicationDraft(TimestampMixin, Base):
    __tablename__ = "communication_drafts"
    offer_id: Mapped[str | None] = mapped_column(ForeignKey("freight_offers.id"), nullable=True)
    shipment_id: Mapped[str | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)
    recipient_type: Mapped[str] = mapped_column(String(20), default="carrier")
    recipient: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language: Mapped[str] = mapped_column(String(2), default="en")
    purpose: Mapped[str] = mapped_column(String(80))
    body: Mapped[str] = mapped_column(Text)
    uncertainties: Mapped[list] = mapped_column(JSON, default=list)
    review_advisable: Mapped[bool] = mapped_column(Boolean, default=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)  # never True in demo


# --------------------------------------------------------------------------- #
# Shipments / monitoring
# --------------------------------------------------------------------------- #
class Shipment(TimestampMixin, Base):
    __tablename__ = "shipments"
    offer_id: Mapped[str | None] = mapped_column(ForeignKey("freight_offers.id"), nullable=True)
    carrier_id: Mapped[str | None] = mapped_column(ForeignKey("carriers.id"), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    reference: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(30), default="created")
    origin: Mapped[str | None] = mapped_column(String(160), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(160), nullable=True)
    carrier_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    sell_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    milestones: Mapped[list[ShipmentMilestone]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )


class ShipmentMilestone(TimestampMixin, Base):
    __tablename__ = "shipment_milestones"
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    name: Mapped[str] = mapped_column(String(60))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    shipment: Mapped[Shipment] = relationship(back_populates="milestones")


class TrackingEvent(TimestampMixin, Base):
    __tablename__ = "tracking_events"
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    event_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(40), default="mock")


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"
    shipment_id: Mapped[str | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    message: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    shipment_id: Mapped[str | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)
    carrier_id: Mapped[str | None] = mapped_column(ForeignKey("carriers.id"), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signatures_present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stamp_present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    readable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    missing_pages: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentCheck(TimestampMixin, Base):
    __tablename__ = "document_checks"
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    shipment_id: Mapped[str | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)
    completeness: Mapped[str] = mapped_column(String(20), default="incomplete")
    missing: Mapped[list] = mapped_column(JSON, default=list)
    inconsistencies: Mapped[list] = mapped_column(JSON, default=list)
    review_needed: Mapped[bool] = mapped_column(Boolean, default=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #
class KnowledgeNote(TimestampMixin, Base):
    __tablename__ = "knowledge_notes"
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provenance: Mapped[str] = mapped_column(String(20), default="user_entered")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)


# --------------------------------------------------------------------------- #
# Approvals, integrations, audit, agent runs
# --------------------------------------------------------------------------- #
class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"
    action: Mapped[str] = mapped_column(String(80))
    external_system: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    source_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class IntegrationConfig(TimestampMixin, Base):
    __tablename__ = "integration_configs"
    name: Mapped[str] = mapped_column(String(40), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    read_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    write_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mock_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    credential_status: Mapped[str] = mapped_column(String(20), default="not_configured")
    last_successful_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_failure: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(TimestampMixin, Base):
    __tablename__ = "audit_events"
    actor: Mapped[str] = mapped_column(String(80), default="system")
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"
    agent: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), default="deterministic")
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)


class AgentRecommendation(TimestampMixin, Base):
    __tablename__ = "agent_recommendations"
    agent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    agent: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class FeatureFlag(TimestampMixin, Base):
    __tablename__ = "feature_flags"
    name: Mapped[str] = mapped_column(String(60), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
