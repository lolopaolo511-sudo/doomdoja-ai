"""
computer_use/desktop.py — read-only świadomość pulpitu.

Funkcja desktop_screenshot() robi screenshot całego ekranu przez macOS
`screencapture` — TYLKO odczyt, bez klikania w system.

Przydatność dla agenta: weryfikacja co jest wyświetlone na ekranie użytkownika,
orientacja w środowisku pracy, pomoc kontekstualna.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

_SHOT_DIR = Path(os.path.expanduser("~/.qwen_agent/screenshots"))
_SHOT_DIR.mkdir(parents=True, exist_ok=True)


def desktop_screenshot(name: str | None = None) -> dict:
    """
    Zrób screenshot pulpitu (tylko odczyt, bez interakcji z systemem).

    Returns:
        {"success": bool, "path": str, "message": str}
    """
    fname = name or f"desktop_{int(time.time())}.png"
    if not fname.endswith(".png"):
        fname += ".png"
    path = _SHOT_DIR / fname

    try:
        result = subprocess.run(
            ["screencapture", "-x", str(path)],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {
                "success": False,
                "path": "",
                "message": f"screencapture błąd: {result.stderr.decode()[:200]}",
            }
        return {
            "success": True,
            "path": str(path),
            "message": f"Screenshot pulpitu zapisany: {path}",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "path": "",
            "message": "screencapture nie dostępne (tylko macOS)",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "path": "",
            "message": "screencapture timeout (10s)",
        }


# ── Tool spec dla rejestru agenta ─────────────────────────────────────────────

DESKTOP_TOOL_SPEC = {
    "name": "desktop_screenshot",
    "description": (
        "Zrób read-only screenshot pulpitu macOS przez screencapture. "
        "TYLKO podgląd — nie klika ani nie wchodzi w interakcję z systemem."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string",
                     "description": "Nazwa pliku PNG (opcjonalne)"},
        },
    },
}


def desktop_screenshot_tool(params: dict) -> str:
    """Agent tool interface — zwraca string wynikowy."""
    result = desktop_screenshot(params.get("name"))
    if result["success"]:
        return f"[OK] {result['message']}"
    return f"[FAIL] {result['message']}"
