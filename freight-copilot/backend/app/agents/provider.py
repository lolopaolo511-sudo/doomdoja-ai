"""LLM provider abstraction.

The product is fully functional with the *deterministic* provider (no LLM).
LLM providers are an optional ENRICHMENT layer:

  * they polish human-readable text (e.g. communication drafts), and
  * they help parse messy free-text intake into structured fields,

but they NEVER make the safety-critical structured decisions (opportunity
score, carrier risk level, price/margin) — those stay in deterministic rule
code — and they NEVER trigger an external action (that always routes through an
ApprovalRequest). Every LLM call has a deterministic fallback: on any error,
refusal, missing credential or timeout, ``complete()`` returns ``None`` and the
caller uses its rule-based result. The app therefore works offline by default.

Providers:
  - deterministic : no network, rule-based text (default)
  - mock          : reproducible, used by tests (never calls out)
  - local         : OpenAI-compatible local endpoint (e.g. Ollama), gated by flag
  - anthropic     : Anthropic API (claude-sonnet-4-6 for agents), gated by flag
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..config import get_settings


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str | None
    is_llm: bool

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str | None: ...


class DeterministicProvider:
    """Default provider — no network. Returns None so callers use rule output."""

    name = "deterministic"
    model = None
    is_llm = False

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str | None:
        return None


class MockProvider(DeterministicProvider):
    """Reproducible provider for tests. Never calls out."""

    name = "mock"
    model = "mock-1"


class LocalLLMProvider:
    """OpenAI-compatible local endpoint (e.g. Ollama, LM Studio, vLLM).

    Keeps operational data on-box. Falls back to None on any error so the
    deterministic path is always used if the endpoint is unavailable.
    """

    name = "local"
    is_llm = True

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.local_llm_model
        self.base_url = settings.local_llm_base_url.rstrip("/")

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str | None:
        try:
            import httpx

            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return text.strip() or None
        except Exception:
            return None


class AnthropicProvider:
    """Anthropic API adapter (official SDK).

    Uses the configured subagent model (default claude-sonnet-4-6) for in-app
    agent enrichment; the primary orchestration model (claude-opus-4-8) is
    available via ``primary_model``. Reads ANTHROPIC_API_KEY from the
    environment. Returns None on any error or safety refusal so the caller
    falls back to deterministic output.
    """

    name = "anthropic"
    is_llm = True

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.anthropic_subagent_model
        self.primary_model = settings.anthropic_primary_model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str | None:
        try:
            import anthropic

            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
            resp = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            # Safety classifiers / model refusals -> fall back deterministically.
            if getattr(resp, "stop_reason", None) == "refusal":
                return None
            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            ).strip()
            return text or None
        except Exception:
            return None


def get_provider() -> LLMProvider:
    settings = get_settings()
    choice = settings.llm_provider
    if choice == "mock":
        return MockProvider()
    if choice in {"anthropic", "auto"} and settings.anthropic_llm_enabled:
        return AnthropicProvider()
    if choice in {"local", "auto"} and settings.local_llm_enabled:
        return LocalLLMProvider()
    return DeterministicProvider()
