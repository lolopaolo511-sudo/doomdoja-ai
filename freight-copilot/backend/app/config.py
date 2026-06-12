"""Application configuration and feature flags.

Local-first by design: everything works against SQLite with no external
services. Feature flags default to the SAFE position (external reads/writes
disabled). Secrets are read from the environment / .env and are never logged.
"""

from __future__ import annotations

import os
from functools import lru_cache


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Runtime settings derived from environment variables.

    Kept deliberately simple (no hard pydantic-settings dependency at import
    time) so the app can boot in a bare environment for the demo.
    """

    def __init__(self) -> None:
        # --- Core ---
        self.app_name: str = os.environ.get("APP_NAME", "Freight Copilot")
        self.env: str = os.environ.get("APP_ENV", "local")
        self.timezone: str = os.environ.get("APP_TZ", "Europe/Warsaw")
        self.default_currency: str = os.environ.get("DEFAULT_CURRENCY", "EUR")
        self.default_language: str = os.environ.get("DEFAULT_LANGUAGE", "en")

        # --- Database: SQLite by default, Postgres optional via DATABASE_URL ---
        default_sqlite = "sqlite:///./freight_copilot.db"
        self.database_url: str = os.environ.get("DATABASE_URL", default_sqlite)

        # --- Feature flags (SAFE defaults) ---
        self.demo_mode: bool = _flag("DEMO_MODE", True)
        self.external_reads_enabled: bool = _flag("EXTERNAL_READS_ENABLED", False)
        self.external_writes_enabled: bool = _flag("EXTERNAL_WRITES_ENABLED", False)
        self.timocom_enabled: bool = _flag("TIMOCOM_ENABLED", False)
        self.transeu_enabled: bool = _flag("TRANSEU_ENABLED", False)
        self.email_enabled: bool = _flag("EMAIL_ENABLED", False)
        self.tracking_enabled: bool = _flag("TRACKING_ENABLED", False)
        self.local_llm_enabled: bool = _flag("LOCAL_LLM_ENABLED", False)
        self.anthropic_llm_enabled: bool = _flag("ANTHROPIC_LLM_ENABLED", False)

        # --- LLM provider config (all optional) ---
        # Default provider is "deterministic": the product is fully usable with
        # zero LLM calls. "mock" is used by tests for reproducibility.
        self.llm_provider: str = os.environ.get("LLM_PROVIDER", "deterministic")
        self.local_llm_base_url: str = os.environ.get(
            "LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"
        )
        # Model ids used only if the (placeholder) Anthropic adapter is enabled.
        self.anthropic_primary_model: str = os.environ.get(
            "ANTHROPIC_PRIMARY_MODEL", "claude-opus-4-8"
        )
        self.anthropic_subagent_model: str = os.environ.get(
            "ANTHROPIC_SUBAGENT_MODEL", "claude-sonnet-4-6"
        )

        # --- Upload safety limits ---
        self.max_upload_bytes: int = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
        self.allowed_upload_ext: tuple[str, ...] = (
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".csv",
            ".xlsx",
            ".txt",
        )

    def feature_flags(self) -> dict[str, bool]:
        return {
            "DEMO_MODE": self.demo_mode,
            "EXTERNAL_READS_ENABLED": self.external_reads_enabled,
            "EXTERNAL_WRITES_ENABLED": self.external_writes_enabled,
            "TIMOCOM_ENABLED": self.timocom_enabled,
            "TRANSEU_ENABLED": self.transeu_enabled,
            "EMAIL_ENABLED": self.email_enabled,
            "TRACKING_ENABLED": self.tracking_enabled,
            "LOCAL_LLM_ENABLED": self.local_llm_enabled,
            "ANTHROPIC_LLM_ENABLED": self.anthropic_llm_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
