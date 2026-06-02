#!/usr/bin/env python3
"""
Cloud backend — Anthropic Claude API.

Klucz API WYŁĄCZNIE ze zmiennej środowiskowej ANTHROPIC_API_KEY (lub .env).
Jeśli klucz brak → CloudBackend.is_available() = False, generate() rzuca wyjątek
z czytelnym komunikatem (nie zgaduje ani nie hardkoduje kluczy).

Obsługuje zarówno SDK anthropic (jeśli zainstalowany) jak i surowe httpx.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("qwen_agent.router.cloud")

# Nazwa zmiennej domyślnie — można nadpisać w konstruktorze
_DEFAULT_API_KEY_ENV = "ANTHROPIC_API_KEY"
_ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class CloudUnavailableError(Exception):
    """Rzucane gdy cloud backend nie jest dostępny (brak klucza, brak połączenia)."""
    pass


class CloudBackend:
    """
    Wrapper na Anthropic Claude API.

    Kolejność prób:
      1. Pakiet `anthropic` (oficjalny SDK) — jeśli zainstalowany
      2. Surowe httpx — fallback bez dodatkowych zależności

    Użycie:
        backend = CloudBackend()
        if backend.is_available():
            response = backend.generate("napisz pełną aplikację...", model="claude-opus-4-8")
        else:
            print("brak ANTHROPIC_API_KEY — działam local-only")
    """

    def __init__(
        self,
        api_key_env: str = _DEFAULT_API_KEY_ENV,
        model: str = "claude-opus-4-8",
        timeout_s: int = 120,
    ):
        self._api_key_env = api_key_env
        self.default_model = model
        self._timeout = timeout_s
        self._sdk_available = self._check_sdk()

    def is_available(self) -> bool:
        """True jeśli klucz API jest ustawiony."""
        return bool(self._get_api_key())

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        system: str = "You are an expert software engineer. Be concise and correct.",
    ) -> str:
        """
        Wysyła prompt do Anthropic API i zwraca odpowiedź.

        Raises:
            CloudUnavailableError: gdy brak klucza lub połączenia
        """
        api_key = self._get_api_key()
        if not api_key:
            raise CloudUnavailableError(
                f"Cloud backend niedostępny: ustaw zmienną środowiskową {self._api_key_env}"
            )

        target_model = model or self.default_model
        logger.info(f"[cloud] generate model={target_model} prompt_len={len(prompt)}")

        if self._sdk_available:
            return self._generate_sdk(prompt, api_key, target_model, temperature, max_tokens, system)
        return self._generate_httpx(prompt, api_key, target_model, temperature, max_tokens, system)

    # ── PRIVATE ────────────────────────────────────────────────────────────

    def _get_api_key(self) -> str:
        return os.getenv(self._api_key_env, "").strip()

    @staticmethod
    def _check_sdk() -> bool:
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def _generate_sdk(
        self,
        prompt: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system: str,
    ) -> str:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            raise CloudUnavailableError(f"Anthropic SDK error: {e}") from e

    def _generate_httpx(
        self,
        prompt: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system: str,
    ) -> str:
        try:
            import httpx
        except ImportError:
            raise CloudUnavailableError("Ani 'anthropic' SDK ani 'httpx' nie są zainstalowane")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            r = httpx.post(
                _ANTHROPIC_API_URL,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
            return data["content"][0]["text"].strip()
        except Exception as e:
            raise CloudUnavailableError(f"Anthropic API error (httpx): {e}") from e
