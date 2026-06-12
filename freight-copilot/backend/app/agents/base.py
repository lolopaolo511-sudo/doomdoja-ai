"""Shared agent result type and base class."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Structured, explainable output common to every agent.

    No agent returns a bare value: callers always get the data plus the
    reasoning, the confidence, what was missing, and the source — so every
    recommendation is traceable and never presented as fact.
    """

    agent: str
    summary: str
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    missing_fields: list[str] = field(default_factory=list)
    factors: list[str] = field(default_factory=list)
    provider: str = "deterministic"
    model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaseAgent:
    """Base class wiring the provider in and exposing a stable interface."""

    name: str = "base"

    def __init__(self, provider: Any | None = None) -> None:
        # provider is an optional LLMProvider; deterministic logic always works.
        from .provider import get_provider

        self.provider = provider or get_provider()

    def _result(self, **kwargs: Any) -> AgentResult:
        kwargs.setdefault("agent", self.name)
        kwargs.setdefault("provider", getattr(self.provider, "name", "deterministic"))
        kwargs.setdefault("model", getattr(self.provider, "model", None))
        return AgentResult(**kwargs)
