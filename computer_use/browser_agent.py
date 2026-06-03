"""
computer_use/browser_agent.py — ReAct narzędzia do sterowania przeglądarką.

Narzędzia ReAct:
  navigate(url)              → nawiguj do URL (whitelist domen)
  read_page(selector?)       → czytaj zawartość strony / elementu
  click(selector, confirm?)  → kliknij element (confirm=True dla niebezpiecznych)
  type_text(selector, text)  → wpisz tekst w pole
  extract(schema)            → wyodrębnij dane wg JSON schema przez LLM
  screenshot(name?)          → zapisz screenshot strony

Bezpieczniki:
  - Whitelist domen w config.yaml — zablokowane domeny zwracają BLOCKED:
  - Akcje submit/niebezpieczne URL wymagają confirm=True, domyślnie zablokowane
  - Każda akcja logowana do action_log_dir z timestampem i wynikiem
  - NIE uruchamia przeglądarki dopóki nie wywołasz navigate()
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

_CFG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    try:
        import yaml
        with open(_CFG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


_CFG = _load_config()

ALLOWED_DOMAINS: set[str] = set(_CFG.get("allowed_domains", [
    "httpbin.org", "quotes.toscrape.com", "books.toscrape.com",
    "the-internet.herokuapp.com", "example.com", "localhost", "127.0.0.1",
]))

DANGEROUS_PATTERNS: list[str] = _CFG.get("dangerous_url_patterns", [
    "checkout", "payment", "/pay", "/buy", "purchase",
    "submit-order", "delete-account", "/transfer", "/admin", "/delete",
])

_LOG_DIR = Path(os.path.expanduser(
    _CFG.get("action_log_dir", "~/.qwen_agent/computer_use_logs")))
_SHOT_DIR = Path(os.path.expanduser(
    _CFG.get("screenshot_dir", "~/.qwen_agent/screenshots")))
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_SHOT_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE = _LOG_DIR / f"actions_{datetime.now().strftime('%Y%m%d')}.jsonl"


def _log_action(action: str, params: dict, result: "BrowserResult") -> None:
    entry = {
        "ts": datetime.now().isoformat(),
        "action": action,
        "params": {k: v for k, v in params.items() if k != "text" or len(str(v)) < 200},
        "success": result.success,
        "message": result.message[:300],
    }
    with _LOG_FILE.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _domain_allowed(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def _is_dangerous(url: str) -> bool:
    low = url.lower()
    return any(pat in low for pat in DANGEROUS_PATTERNS)


@dataclass
class BrowserResult:
    success: bool
    message: str
    data: dict = field(default_factory=dict)

    def __str__(self) -> str:
        tag = "OK" if self.success else "FAIL"
        base = f"[{tag}] {self.message}"
        if self.data:
            base += f"\n{json.dumps(self.data, ensure_ascii=False)[:800]}"
        return base


class BrowserAgent:
    """
    Sesja przeglądarki z ReAct-friendly API.
    Jeden obiekt = jedna sesja Playwright (lazy init przy pierwszym navigate).
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def _ensure(self) -> None:
        if self._page:
            return
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self._page = await self._browser.new_page()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = self._page = self._pw = None

    # ── ReAct tools ──────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> BrowserResult:
        """Nawiguj do URL. Tylko whitelist domen. Zwraca tytuł i aktualny URL."""
        if not _domain_allowed(url):
            r = BrowserResult(False, f"BLOCKED: domena nie na whiteliście → {url}",
                              {"allowed": sorted(ALLOWED_DOMAINS)})
            _log_action("navigate", {"url": url}, r)
            return r
        await self._ensure()
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            title = await self._page.title()
            r = BrowserResult(True, f"Nawigacja OK → {url}",
                              {"title": title, "url": self._page.url})
        except Exception as e:
            r = BrowserResult(False, f"Błąd nawigacji: {e}")
        _log_action("navigate", {"url": url}, r)
        return r

    async def read_page(self, selector: Optional[str] = None) -> BrowserResult:
        """Czytaj tekst strony (cały body) lub konkretnego elementu."""
        if not self._page:
            return BrowserResult(False, "Brak otwartej strony. Wywołaj navigate() najpierw.")
        try:
            if selector:
                txt = await self._page.text_content(selector, timeout=4_000) or ""
            else:
                txt = await self._page.text_content("body") or ""
            r = BrowserResult(True, f"Odczytano {len(txt)} znaków",
                              {"text": txt[:4000], "selector": selector or "body"})
        except Exception as e:
            r = BrowserResult(False, f"Błąd odczytu: {e}")
        _log_action("read_page", {"selector": selector}, r)
        return r

    async def click(self, selector: str, confirm: bool = False) -> BrowserResult:
        """
        Kliknij element.
        Jeśli aktualny URL zawiera wzorzec niebezpieczny → wymaga confirm=True.
        submit/buy/delete bez confirm=True → BLOCKED.
        """
        if not self._page:
            return BrowserResult(False, "Brak otwartej strony.")
        current_url = self._page.url
        if _is_dangerous(current_url) and not confirm:
            r = BrowserResult(False,
                f"BLOCKED: niebezpieczny URL '{current_url}' — ustaw confirm=True",
                {"url": current_url})
            _log_action("click", {"selector": selector, "confirm": confirm}, r)
            return r
        # Sprawdź czy sam selektor nie wygląda jak submit
        if re.search(r"(submit|buy|pay|delete|send)", selector, re.I) and not confirm:
            r = BrowserResult(False,
                f"BLOCKED: selektor '{selector}' wygląda jak akcja nieodwracalna — confirm=True",
                {"selector": selector})
            _log_action("click", {"selector": selector, "confirm": confirm}, r)
            return r
        try:
            await self._page.click(selector, timeout=5_000)
            r = BrowserResult(True, f"Kliknięto: {selector}",
                              {"url": self._page.url})
        except Exception as e:
            r = BrowserResult(False, f"Błąd kliknięcia: {e}")
        _log_action("click", {"selector": selector, "confirm": confirm}, r)
        return r

    async def type_text(self, selector: str, text: str) -> BrowserResult:
        """Wpisz tekst w pole formularza (fill, nie keystroke)."""
        if not self._page:
            return BrowserResult(False, "Brak otwartej strony.")
        try:
            await self._page.fill(selector, text)
            r = BrowserResult(True, f"Wpisano {len(text)} znaków w {selector}")
        except Exception as e:
            r = BrowserResult(False, f"Błąd type_text: {e}")
        _log_action("type_text", {"selector": selector, "text": text[:50]}, r)
        return r

    async def extract(self, schema: dict) -> BrowserResult:
        """
        Wyodrębnij dane ze strony wg JSON schema używając lokalnego LLM.
        schema: {"field_name": "opis co wyodrębnić", ...}
        Zwraca dict z wyodrębnionymi wartościami.
        """
        if not self._page:
            return BrowserResult(False, "Brak otwartej strony.")
        try:
            page_text = (await self._page.text_content("body") or "")[:3000]
        except Exception as e:
            return BrowserResult(False, f"Błąd odczytu strony do extract: {e}")

        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        prompt = (
            f"Wyodrębnij dane ze strony wg poniższego schematu.\n"
            f"SCHEMA:\n{schema_str}\n\n"
            f"TREŚĆ STRONY (pierwsze 3000 znaków):\n{page_text}\n\n"
            f"Odpowiedz TYLKO prawidłowym JSON z kluczami z schema. "
            f"Jeśli nie znalazłeś wartości → null."
        )
        extracted = self._call_llm_sync(prompt)
        try:
            data = json.loads(re.search(r"\{.*\}", extracted, re.S).group())
            r = BrowserResult(True, f"Wyodrębniono {len(data)} pól", {"extracted": data})
        except Exception:
            r = BrowserResult(True, "Ekstrakcja (raw LLM)",
                              {"raw": extracted[:500], "extracted": {}})
        _log_action("extract", {"schema_keys": list(schema.keys())}, r)
        return r

    async def screenshot(self, name: Optional[str] = None) -> BrowserResult:
        """Zapisz screenshot bieżącej strony do pliku PNG."""
        if not self._page:
            return BrowserResult(False, "Brak otwartej strony.")
        fname = name or f"browser_{int(time.time())}.png"
        if not fname.endswith(".png"):
            fname += ".png"
        path = _SHOT_DIR / fname
        try:
            await self._page.screenshot(path=str(path))
            r = BrowserResult(True, f"Screenshot zapisany: {path}",
                              {"path": str(path)})
        except Exception as e:
            r = BrowserResult(False, f"Screenshot błąd: {e}")
        _log_action("screenshot", {"name": fname}, r)
        return r

    # ── helper ───────────────────────────────────────────────────────────────

    def _call_llm_sync(self, prompt: str) -> str:
        """Wywołaj lokalny LLM do extract() — synchronicznie przez httpx."""
        model = _CFG.get("extract_model", "deepseek-coder-v2:16b")
        timeout = _CFG.get("extract_timeout_s", 60)
        try:
            import httpx
            r = httpx.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.0}},
                timeout=timeout,
            )
            return r.json().get("response", "")
        except Exception as e:
            return f"[LLM error: {e}]"

    # ── sync wrapper dla ReAct agent ─────────────────────────────────────────

    def run(self, action: str, **kwargs) -> BrowserResult:
        """Synchroniczny dispatch — używany przez ReAct agent tool handler."""
        coro_map = {
            "navigate": self.navigate,
            "read_page": self.read_page,
            "click": self.click,
            "type_text": self.type_text,
            "extract": self.extract,
            "screenshot": self.screenshot,
        }
        if action not in coro_map:
            return BrowserResult(False, f"Nieznana akcja: {action}. "
                                 f"Dostępne: {list(coro_map)}")
        coro_fn = coro_map[action]
        return asyncio.run(coro_fn(**kwargs))

    def __call__(self, params: dict) -> str:
        """Agent tool interface — przyjmuje dict params, zwraca str."""
        action = params.pop("action", "")
        result = self.run(action, **params)
        return str(result)


# ── ReAct tool specs (dla rejestru agenta) ────────────────────────────────────

COMPUTER_USE_TOOLS: list[dict] = [
    {
        "name": "navigate",
        "description": "Nawiguj przeglądarką do URL. Tylko domeny z whitelist.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Pełny URL do odwiedzenia"}},
            "required": ["url"],
        },
    },
    {
        "name": "read_page",
        "description": "Czytaj tekst bieżącej strony lub elementu (selector CSS/XPath).",
        "parameters": {
            "type": "object",
            "properties": {"selector": {"type": "string",
                           "description": "CSS/XPath selector (opcjonalne, domyślnie: cały body)"}},
        },
    },
    {
        "name": "click",
        "description": "Kliknij element na stronie. Niebezpieczne akcje wymagają confirm=True.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "confirm": {"type": "boolean",
                            "description": "Wymagane=True dla submit/buy/delete"},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "type_text",
        "description": "Wpisz tekst w pole formularza.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector pola"},
                "text": {"type": "string", "description": "Tekst do wpisania"},
            },
            "required": ["selector", "text"],
        },
    },
    {
        "name": "extract",
        "description": (
            "Wyodrębnij strukturalne dane ze strony wg JSON schema przez lokalny LLM. "
            'schema = {"pole": "co wyodrębnić"}'
        ),
        "parameters": {
            "type": "object",
            "properties": {"schema": {"type": "object",
                           "description": "Dict {nazwa_pola: opis_co_wyodrebnić}"}},
            "required": ["schema"],
        },
    },
    {
        "name": "screenshot",
        "description": "Zapisz screenshot bieżącej strony przeglądarki.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string",
                           "description": "Nazwa pliku PNG (opcjonalne)"}},
        },
    },
]
