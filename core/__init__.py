"""
qwen-agent.core

Hardened shared infrastructure for the entire doomdoja AI platform.

- config: central StackConfig (paths, models, services)
- llm_client: single robust client for generate/embed/vision + JSON extraction
"""

from .config import get_config, StackConfig, reload_config
from .llm_client import (
    LLMClient,
    LLMClientError,
    get_llm_client,
    reset_llm_client,
)

__all__ = [
    "get_config",
    "StackConfig",
    "reload_config",
    "LLMClient",
    "LLMClientError",
    "get_llm_client",
    "reset_llm_client",
]
