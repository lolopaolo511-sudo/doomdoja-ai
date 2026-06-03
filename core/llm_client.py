"""
Hardened, unified LLM client for the entire doomdoja AI stack.

Replaces dozens of duplicated raw httpx calls.

Features:
- Automatic retries with exponential backoff (tenacity)
- Robust JSON extraction + optional repair attempts
- Unified interface for generate / embed / vision
- Structured logging of calls (optional)
- Timeouts, temperature, model overrides per call
- Graceful degradation on transient errors
- Single place to tune behavior for the whole system

Usage:
    from qwen_agent.core.llm_client import LLMClient, get_llm_client
    from qwen_agent.core.config import get_config

    llm = get_llm_client()
    resp = llm.generate("Explain Python decorators in 3 bullets", temperature=0.3)

    # Structured
    data = llm.extract_json("Return a JSON object with name and age", schema_hint="person")

    # Vision
    desc = llm.vision_generate("screenshot.png", "Describe this UI in detail")

    # Embeddings
    vec = llm.embed("some text for retrieval")
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

import httpx

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_sleep_log,
    )
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

from .config import get_config, StackConfig

logger = logging.getLogger("qwen_agent.llm_client")


class LLMClientError(Exception):
    """Base error for LLM client issues."""
    pass


class LLMClient:
    def __init__(self, config: Optional[StackConfig] = None):
        self.cfg = config or get_config()
        self._client = httpx.Client(timeout=self.cfg.ollama_timeout_s)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ─────────────────────────────────────────────────────────────────────
    # Public high-level API
    # ─────────────────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        images: Optional[list[str | Path]] = None,  # base64 or paths for vision
        stream: bool = False,  # kept for future; currently False only
    ) -> str:
        """Main text generation entrypoint. Retries on transient failure."""
        model = model or self.cfg.default_coder_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if images:
            payload["images"] = [self._prepare_image(i) for i in images]

        data = self._post_with_retry(
            f"{self.cfg.ollama_url}/api/generate",
            json=payload,
            timeout=timeout or self.cfg.ollama_timeout_s,
        )
        return data.get("response", "").strip()

    def embed(
        self,
        text: str | list[str],
        *,
        model: Optional[str] = None,
    ) -> list[float] | list[list[float]]:
        """Get embedding vector(s). Returns list[float] for single text."""
        model = model or self.cfg.embed_model
        is_batch = isinstance(text, list)
        payload = {"model": model, "input": text if is_batch else [text]}

        data = self._post_with_retry(
            f"{self.cfg.ollama_url}/api/embed",
            json=payload,
            timeout=60,
        )

        embeddings = data.get("embeddings") or data.get("embedding")
        if embeddings is None:
            raise LLMClientError(f"No embeddings in response: {data}")

        if is_batch:
            return embeddings
        return embeddings[0] if isinstance(embeddings, list) else embeddings

    def vision_generate(
        self,
        image: str | Path,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        """Vision / multimodal generation (llava etc.)."""
        model = model or self.cfg.vision_model
        b64 = self._prepare_image(image)

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
            "options": {"temperature": temperature},
        }

        data = self._post_with_retry(
            f"{self.cfg.ollama_url}/api/generate",
            json=payload,
            timeout=self.cfg.ollama_timeout_s,
        )
        return data.get("response", "").strip()

    # ─────────────────────────────────────────────────────────────────────
    # Structured output helpers (the main source of previous fragility)
    # ─────────────────────────────────────────────────────────────────────

    def extract_json(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_attempts: int = 2,
        schema_hint: str = "",
    ) -> dict | list:
        """
        Ask the model for JSON and robustly extract + validate it.
        On failure, makes a repair attempt with the previous bad output.
        """
        base_prompt = prompt
        if schema_hint:
            base_prompt += f"\n\nSchema hint: {schema_hint}\nReturn ONLY valid JSON."

        last_raw = ""
        for attempt in range(1, max_attempts + 1):
            raw = self.generate(
                base_prompt if attempt == 1 else self._repair_prompt(base_prompt, last_raw),
                model=model or self.cfg.default_fast_model,
                temperature=temperature,
            )
            last_raw = raw

            parsed = self._parse_json_robust(raw)
            if parsed is not None:
                return parsed

            logger.warning(f"JSON parse failed on attempt {attempt}/{max_attempts}")

        raise LLMClientError(f"Failed to extract valid JSON after {max_attempts} attempts. Last raw:\n{last_raw[:500]}")

    def extract_code_block(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        temperature: float = 0.15,
        language: str = "python",
    ) -> str:
        """Extract a ```language ... ``` block. Falls back to whole response cleaned."""
        raw = self.generate(prompt, model=model, temperature=temperature)
        match = re.search(rf"```{language}\n(.*?)```", raw, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Fallback: strip any ``` markers
        cleaned = re.sub(r"```[a-z]*\n?", "", raw, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        return cleaned

    # ─────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────

    def _post_with_retry(self, url: str, *, json: dict, timeout: int) -> dict:
        """POST with optional tenacity retry."""
        if HAS_TENACITY:
            return self._post_retry_tenacity(url, json=json, timeout=timeout)
        else:
            return self._post_simple(url, json=json, timeout=timeout)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _post_retry_tenacity(self, url: str, *, json: dict, timeout: int) -> dict:
        r = self._client.post(url, json=json, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def _post_simple(self, url: str, *, json: dict, timeout: int) -> dict:
        last_exc = None
        for attempt in range(1, self.cfg.llm_retries + 1):
            try:
                r = self._client.post(url, json=json, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_exc = e
                if attempt < self.cfg.llm_retries:
                    sleep = self.cfg.llm_retry_backoff ** (attempt - 1)
                    logger.warning(f"LLM call failed (attempt {attempt}), retrying in {sleep:.1f}s: {e}")
                    time.sleep(sleep)
        raise LLMClientError(f"LLM call failed after {self.cfg.llm_retries} attempts: {last_exc}") from last_exc

    def _prepare_image(self, image: str | Path) -> str:
        """Accept path or already-base64 string. Return base64."""
        if isinstance(image, (str, Path)):
            p = Path(image)
            if p.exists():
                import base64
                return base64.b64encode(p.read_bytes()).decode()
            # Assume it's already base64
            return str(image)
        return str(image)

    def _parse_json_robust(self, text: str) -> Optional[dict | list]:
        """Try multiple strategies to extract JSON from noisy LLM output."""
        text = text.strip()

        # 1. Direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2. Find first { ... } or [ ... ] block
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, text, re.DOTALL)
            if match:
                candidate = match.group(0)
                try:
                    return json.loads(candidate)
                except Exception:
                    # 3. Try to repair common issues (trailing commas, etc.)
                    repaired = self._simple_json_repair(candidate)
                    try:
                        return json.loads(repaired)
                    except Exception:
                        pass
        return None

    def _simple_json_repair(self, bad_json: str) -> str:
        """Very lightweight repair for common LLM JSON mistakes."""
        s = bad_json
        # Remove trailing commas before } or ]
        s = re.sub(r",\s*([}\]])", r"\1", s)
        # Remove comments (rare but happens)
        s = re.sub(r"//.*?\n|/\*.*?\*/", "", s, flags=re.DOTALL)
        return s

    def _repair_prompt(self, original_prompt: str, bad_output: str) -> str:
        return (
            f"{original_prompt}\n\n"
            f"Previous attempt produced invalid JSON:\n{bad_output[:800]}\n\n"
            "Fix the output and return ONLY valid JSON. No explanations."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience singleton (most code will use this)
# ─────────────────────────────────────────────────────────────────────────────

_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def reset_llm_client():
    """For tests or config reloads."""
    global _default_client
    if _default_client:
        _default_client.close()
    _default_client = None
