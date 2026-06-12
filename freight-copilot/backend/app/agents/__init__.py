"""Operational agents for Freight Copilot.

Each agent is a deterministic, rule-based service with a structured input and
output, a confidence score, explicit missing-field handling and audit logging.
An optional LLMProvider can enrich human-readable summaries, but no agent may
trigger an external write — that always routes through an ApprovalRequest.
"""

from .base import AgentResult
from .carrier_matching import CarrierMatchingAgent
from .carrier_risk import CarrierRiskAgent
from .communication import CommunicationAgent
from .document_controller import DocumentControllerAgent
from .intake import IntakeAgent
from .knowledge_base import KnowledgeBaseAgent
from .monitoring import MonitoringAgent
from .pricing import PricingAgent
from .safety_supervisor import SafetySupervisorAgent
from .scout import ScoutAgent

__all__ = [
    "AgentResult",
    "IntakeAgent",
    "ScoutAgent",
    "PricingAgent",
    "CarrierMatchingAgent",
    "CarrierRiskAgent",
    "CommunicationAgent",
    "MonitoringAgent",
    "DocumentControllerAgent",
    "KnowledgeBaseAgent",
    "SafetySupervisorAgent",
]
