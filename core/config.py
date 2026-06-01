"""
Central configuration for the doomdoja AI stack.

Single source of truth for:
- Paths (no more hardcoded /Users/doomdoja or Path.home() everywhere)
- Default models
- Ollama / service URLs
- Environment loading

Usage:
    from qwen_agent.core.config import get_config
    cfg = get_config()
    print(cfg.ollama_url)
    print(cfg.default_coder_model)
    mem_db = cfg.memory_db_path
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _find_project_root() -> Path:
    """Walk up from this file to find the qwen-agent root (or repo root)."""
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        if (parent / "multiagent").is_dir() and (parent / "prompt-library").is_dir():
            return parent
        # Also support running from inside a monorepo root
        if (parent / "qwen-agent" / "multiagent").is_dir():
            return parent / "qwen-agent"
    # Fallback: two levels up from core/
    return here.parent.parent


@dataclass
class StackConfig:
    project_root: Path = field(default_factory=_find_project_root)

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_timeout_s: int = 180

    # Default models (can be overridden per profile or call)
    default_coder_model: str = "deepseek-coder-v2:16b"
    default_fast_model: str = "qwen2.5-coder:7b"
    embed_model: str = "nomic-embed-text"
    vision_model: str = "llava:7b"

    # Paths (all relative to project_root or explicit)
    memory_db_path: Path = field(init=False)
    tasks_pending_dir: Path = field(init=False)
    tasks_done_dir: Path = field(init=False)
    tasks_failed_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    prompt_library_dir: Path = field(init=False)

    # External services (override via env)
    searxng_url: str = "http://localhost:8888"
    qdrant_url: str = "http://localhost:6333"
    make_webhook_url: Optional[str] = None

    # Airtable (loaded from env, never committed)
    airtable_pat: Optional[str] = None
    airtable_base_id: Optional[str] = None

    # Feature flags / hardening
    llm_retries: int = 3
    llm_retry_backoff: float = 1.5
    strict_json_mode: bool = True  # try to force/repair JSON

    def __post_init__(self):
        root = self.project_root

        self.memory_db_path = root / "agent_memory.db"
        self.tasks_pending_dir = root / "tasks" / "pending"
        self.tasks_done_dir = root / "tasks" / "done"
        self.tasks_failed_dir = root / "tasks" / "failed"
        self.logs_dir = root / "logs"
        self.prompt_library_dir = root / "prompt-library"

        # Load from environment (override defaults)
        self.ollama_url = os.getenv("OLLAMA_URL", self.ollama_url)
        self.searxng_url = os.getenv("SEARXNG_URL", self.searxng_url)
        self.qdrant_url = os.getenv("QDRANT_URL", self.qdrant_url)
        self.make_webhook_url = os.getenv("MAKE_WEBHOOK_URL") or self.make_webhook_url

        self.airtable_pat = os.getenv("AIRTABLE_PAT") or os.getenv("AIRTABLE_API_KEY")
        self.airtable_base_id = os.getenv("AIRTABLE_BASE_ID")

        # Model overrides
        self.default_coder_model = os.getenv("DEFAULT_CODER_MODEL", self.default_coder_model)
        self.default_fast_model = os.getenv("DEFAULT_FAST_MODEL", self.default_fast_model)
        self.embed_model = os.getenv("EMBED_MODEL", self.embed_model)
        self.vision_model = os.getenv("VISION_MODEL", self.vision_model)

        # Retries
        self.llm_retries = int(os.getenv("LLM_RETRIES", self.llm_retries))
        self.llm_retry_backoff = float(os.getenv("LLM_RETRY_BACKOFF", self.llm_retry_backoff))


_config: Optional[StackConfig] = None


def get_config() -> StackConfig:
    """Singleton config (lazy)."""
    global _config
    if _config is None:
        _config = StackConfig()
    return _config


def reload_config() -> StackConfig:
    """Force reload (useful in tests or after env changes)."""
    global _config
    _config = None
    return get_config()
