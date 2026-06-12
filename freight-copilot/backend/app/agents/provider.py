"""LLM provider abstraction.

The product is fully functional with the *deterministic* provider (no LLM).
Other providers are optional enrichment layers for human-readable summaries
only. CRITICAL: a provider is never allowed to perform actions — it returns
text. All structured decisions come from deterministic rule code, and all
external actions route through ApprovalRequest.

Providers:
  - deterministic : returns templated summaries; zero external calls (default)
  - mock          : deterministic + reproducible, used by tests
  - local         : OpenAI-compatible local endpoint (placeholder, gated by flag)
  - anthropic     : Anthropic API (placeholder, gated by flag)
"""

from __future__ import annotations

from typing import Protocol

from ..config import get_settings


class LLMProvider(Protocol):
    name: str
    model: str | None

    def summarize(self, prompt: str, context: dict) -> str: ...


class DeterministicProvider:
    """Default provider — produces summaries from templates, no network."""

    name = "deterministic"
    model = None

    def summarize(self, prompt: str, context: dict) -> str:
        # The deterministic provider simply echoes the prepared summary the
        # agent already computed; agents pass their human-readable text in.
        return context.get("summary", prompt)


class MockProvider(DeterministicProvider):
    """Reproducible provider for tests."""

    name = "mock"
    model = "mock-1"


class LocalLLMProvider:
    """Placeholder for an OpenAI-compatible local endpoint (e.g. Ollama).

    Intentionally not wired to the network in the MVP. When LOCAL_LLM_ENABLED
    is set, integrate an OpenAI-compatible client here. Falls back to
    deterministic text so the app never breaks if the endpoint is down.
    """

    name = "local"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = "local-openai-compatible"
        self.base_url = settings.local_llm_base_url

    def summarize(self, prompt: str, context: dict) -> str:  # pragma: no cover
        # Placeholder: real implementation would POST to self.base_url.
        return context.get("summary", prompt)


class AnthropicProvider:
    """Placeholder for the Anthropic API adapter.

    Gated by ANTHROPIC_LLM_ENABLED. Primary orchestration model id and the
    subagent model id are read from settings. Not wired in the MVP; returns
    deterministic text so behaviour stays safe and offline by default.
    """

    name = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.anthropic_primary_model
        self.subagent_model = settings.anthropic_subagent_model

    def summarize(self, prompt: str, context: dict) -> str:  # pragma: no cover
        return context.get("summary", prompt)


def get_provider() -> LLMProvider:
    settings = get_settings()
    choice = settings.llm_provider
    if choice == "mock":
        return MockProvider()
    if choice == "local" and settings.local_llm_enabled:
        return LocalLLMProvider()
    if choice == "anthropic" and settings.anthropic_llm_enabled:
        return AnthropicProvider()
    return DeterministicProvider()
