#!/usr/bin/env python3
"""
Backward-compatible thin wrapper around the new hardened LLM client.

All existing imports `from llm import call_llm` continue to work.
New code should prefer: `from core.llm_client import get_llm_client`
"""

import sys as _sys
from pathlib import Path as _Path
# Upewnij się że katalog główny projektu jest w sys.path (~/qwen-agent),
# żeby "from core import ..." działało niezależnie od CWD.
_ROOT = str(_Path(__file__).parent.parent)
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

from core import get_llm_client  # noqa: E402

# Legacy constants kept for compatibility
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "deepseek-coder-v2:16b"


def call_llm(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.2) -> str:
    """
    Legacy function — now powered by the hardened client (retries, better errors, etc.).
    """
    llm = get_llm_client()
    return llm.generate(prompt, model=model, temperature=temperature)
