"""
Hybrid Router — automatyczny wybór backend LLM (local/cloud) per zadanie.

Szybki import:
    from router import choose_model, RouterContext, HybridRouter, get_router
"""

from .router import (
    HybridRouter,
    RouterContext,
    RouterDecision,
    choose_model,
    get_router,
    reset_router,
)

__all__ = [
    "HybridRouter",
    "RouterContext",
    "RouterDecision",
    "choose_model",
    "get_router",
    "reset_router",
]
