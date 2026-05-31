#!/usr/bin/env python3
"""Wspólny klient LLM dla wszystkich ról multi-agenta."""

import httpx

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "deepseek-coder-v2:16b"


def call_llm(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.2) -> str:
    r = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False,
              "options": {"temperature": temperature}},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["response"].strip()
