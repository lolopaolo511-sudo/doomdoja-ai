#!/usr/bin/env python3
"""
Diagnostyka całego stacku doomdoja-ai.

Uruchomienie:
    python3 check_health.py

Sprawdza:
  - Ollama (lokalny LLM)
  - ANTHROPIC_API_KEY (cloud fallback)
  - GITHUB_TOKEN / gh CLI (git push / PR)
  - SearxNG (wyszukiwanie)
  - Qdrant (vector DB)
  - MCP server (import)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Załaduj .env jeśli istnieje
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str, hint: str = "") -> None:
    print(f"  {RED}✗{RESET} {msg}")
    if hint:
        print(f"    {YELLOW}→ {hint}{RESET}")


def warn(msg: str, hint: str = "") -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")
    if hint:
        print(f"    {YELLOW}→ {hint}{RESET}")


def check_ollama() -> bool:
    print(f"\n{BOLD}[1] Ollama (lokalny LLM){RESET}")
    url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    if not _HAS_HTTPX:
        warn("httpx niedostępny, pomijam test Ollama", "pip install httpx")
        return False
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        ok(f"Ollama działa ({url})")
        if models:
            ok(f"Modele: {', '.join(models[:5])}")
        else:
            warn("Brak zainstalowanych modeli", "ollama pull deepseek-coder-v2:16b")
        return True
    except Exception as e:
        fail(f"Ollama niedostępna: {e}", f"Uruchom: ollama serve  (lub sprawdź {url})")
        return False


def check_anthropic() -> bool:
    print(f"\n{BOLD}[2] ANTHROPIC_API_KEY (cloud fallback){RESET}")
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        warn(
            "ANTHROPIC_API_KEY nie jest ustawiony — router działa w trybie LOCAL-ONLY",
            "Dodaj do ~/.env: ANTHROPIC_API_KEY=sk-ant-...\n"
            "    Wygeneruj na: https://console.anthropic.com/settings/keys",
        )
        return False
    if not key.startswith("sk-ant-"):
        warn("ANTHROPIC_API_KEY ma nieoczekiwany format (oczekiwano sk-ant-...)")
        return False
    ok(f"ANTHROPIC_API_KEY ustawiony ({key[:12]}...)")
    return True


def check_github() -> bool:
    print(f"\n{BOLD}[3] GitHub auth (push / PR){RESET}")
    passed = False

    # Sprawdź GITHUB_TOKEN
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if token:
        ok(f"GITHUB_TOKEN ustawiony ({token[:8]}...)")
        # Prosty test przez API
        if _HAS_HTTPX:
            try:
                r = httpx.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}",
                             "Accept": "application/vnd.github+json"},
                    timeout=8,
                )
                if r.status_code == 200:
                    login = r.json().get("login", "?")
                    ok(f"Token ważny — konto: {login}")
                    passed = True
                elif r.status_code == 401:
                    fail("Token GITHUB_TOKEN wygasł lub nieważny",
                         "Wygeneruj nowy na: https://github.com/settings/tokens/new")
                else:
                    warn(f"GitHub API zwróciło status {r.status_code}")
            except Exception as e:
                warn(f"Nie można sprawdzić tokena przez sieć: {e}")
        else:
            warn("httpx niedostępny — nie weryfikuję tokena przez API")
            passed = True
    else:
        warn("GITHUB_TOKEN nie ustawiony", "Dodaj do ~/.env: GITHUB_TOKEN=ghp_...")

    # Sprawdź gh CLI
    try:
        r = subprocess.run(
            ["gh", "auth", "status", "--hostname", "github.com"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            ok("gh CLI: zalogowany")
            passed = True
        else:
            err_out = (r.stdout + r.stderr).strip()
            if "not logged" in err_out.lower() or "no token" in err_out.lower() or "expired" in err_out.lower():
                fail("gh CLI: token wygasł lub brak logowania",
                     "Uruchom na Mac Mini:  gh auth login -h github.com")
            else:
                warn(f"gh CLI status nieznany: {err_out[:120]}")
    except FileNotFoundError:
        warn("gh CLI nie zainstalowane", "brew install gh  (opcjonalne)")
    except subprocess.TimeoutExpired:
        warn("gh CLI: timeout")

    if not passed:
        fail("Brak działającego uwierzytelnienia GitHub — push/PR nie zadziała")
    return passed


def check_service(name: str, url: str, check_num: int) -> bool:
    print(f"\n{BOLD}[{check_num}] {name}{RESET}")
    if not _HAS_HTTPX:
        warn("httpx niedostępny, pomijam test", "pip install httpx")
        return False
    try:
        r = httpx.get(url, timeout=5, follow_redirects=True)
        ok(f"{name} działa ({url}) — status {r.status_code}")
        return True
    except Exception as e:
        warn(f"{name} niedostępny: {e}", f"Czy Docker stack jest uruchomiony? (cd doomdoja-stack && docker compose up -d)")
        return False


def check_mcp() -> bool:
    print(f"\n{BOLD}[6] MCP Server (import){RESET}")
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from mcp.server import MCPServer, TOOL_DEFINITIONS
        s = MCPServer()
        ok(f"MCP Server importuje się poprawnie ({len(TOOL_DEFINITIONS)} narzędzi)")
        tools = [t["name"] for t in TOOL_DEFINITIONS]
        ok(f"Narzędzia: {', '.join(tools)}")
        return True
    except Exception as e:
        fail(f"MCP Server błąd importu: {e}")
        return False


def main() -> None:
    print(f"\n{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  doomdoja-ai — diagnostyka stacku{RESET}")
    print(f"{BOLD}{'='*55}{RESET}")

    results = {
        "ollama": check_ollama(),
        "anthropic": check_anthropic(),
        "github": check_github(),
        "searxng": check_service("SearxNG", os.getenv("SEARXNG_URL", "http://localhost:8888"), 4),
        "qdrant": check_service("Qdrant", f"{os.getenv('QDRANT_URL', 'http://localhost:6333')}/healthz", 5),
        "mcp": check_mcp(),
    }

    passed = sum(results.values())
    total = len(results)

    print(f"\n{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  Wynik: {passed}/{total} komponentów OK{RESET}")
    print(f"{BOLD}{'='*55}{RESET}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"\n  {RED}Do naprawy:{RESET} {', '.join(failed)}")

    print()


if __name__ == "__main__":
    main()
