#!/usr/bin/env python3
"""
Local backend — cienki wrapper na istniejący LLMClient (Ollama).

Nowe wywołania mogą używać tego backendu bezpośrednio gdy router
zdecyduje backend="local".
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

# Upewnij się że root projektu jest w path
_ROOT = str(Path(__file__).parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.llm_client import LLMClient, get_llm_client

logger = logging.getLogger("qwen_agent.router.local")


class LocalBackend:
    """
    Wrapper wokół istniejącego LLMClient (Ollama).

    Użycie:
        backend = LocalBackend()
        response = backend.generate("napisz parser CSV", model="deepseek-coder-v2:16b")
    """

    def __init__(self, client: Optional[LLMClient] = None):
        self._client = client or get_llm_client()

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generuje odpowiedź przez lokalny model Ollama."""
        logger.debug(f"[local] generate model={model or 'default'} prompt_len={len(prompt)}")
        return self._client.generate(
            prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def extract_json(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        schema_hint: str = "",
    ) -> dict | list:
        """Ekstrakcja JSON przez lokalny model."""
        return self._client.extract_json(
            prompt,
            model=model,
            temperature=temperature,
            schema_hint=schema_hint,
        )

    def is_available(self) -> bool:
        """Sprawdza czy Ollama jest osiągalna."""
        try:
            import httpx
            cfg = self._client.cfg
            r = httpx.get(f"{cfg.ollama_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"[local] Ollama niedostępna: {e}")
            return False
