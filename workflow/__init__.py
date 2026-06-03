"""
workflow — warstwa orkiestracji dla doomdoja-ai stack.

Prymitywy:
    agent()     subagent z izolowanym kontekstem i budżetem tokenów
    parallel()  N agentów równolegle (bariera: czeka na wszystkie)
    pipeline()  dane płyną przez etapy sekwencyjnie

Wzorce (workflow/patterns/):
    classify_and_act          klasyfikacja → routing do agenta
    fan_out_and_synthesize    N równoległych → 1 synteza
    adversarial_verification  niezależny weryfikator bez wiedzy o autorze
    generate_and_filter       generuj opcje → filtruj rubryką + dedup
    tournament                parami porównaj → ranking
    loop_until_done           iteruj aż warunek spełniony

Bezpieczeństwo:
    WorkflowBudget   twardy limit tokenów (workflow + per-agent)
    quarantine()     tryb tylko-odczyt dla agentów z niezaufanymi danymi
    action_tool      dekorator blokujący akcje w kwarantannie
"""

from .primitives import agent, parallel, pipeline, AgentResult
from .budget import WorkflowBudget, TokenBudgetExceeded, estimate_tokens
from .quarantine import quarantine, is_quarantined, action_tool, QuarantineViolation
from .runner import run_workflow, WorkflowConfig, RunResult, config_from_args

__all__ = [
    "agent",
    "parallel",
    "pipeline",
    "AgentResult",
    "WorkflowBudget",
    "TokenBudgetExceeded",
    "estimate_tokens",
    "quarantine",
    "is_quarantined",
    "action_tool",
    "QuarantineViolation",
    "run_workflow",
    "WorkflowConfig",
    "RunResult",
    "config_from_args",
]
