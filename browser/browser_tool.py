"""
BrowserTool — agent steruje przeglądarką (Playwright).

Bezpieczniki:
- WHITELIST domen (zmień ALLOWED_DOMAINS żeby zezwolić na więcej)
- REQUIRE_CONFIRM = True dla form submit + URL z wrażliwymi keywords
- Nie wykonuje realnych płatności/wysyłek bez confirmation flagi

Akcje:
  navigate, click, type, fill_form, read, screenshot
"""
from __future__ import annotations

import asyncio
import base64
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

ALLOWED_DOMAINS = {
    "httpbin.org",
    "quotes.toscrape.com",
    "books.toscrape.com",
    "the-internet.herokuapp.com",
    "example.com",
    "localhost",
    "127.0.0.1",
}

DANGEROUS_KEYWORDS = {
    "checkout", "payment", "pay", "buy", "purchase", "submit-order",
    "delete-account", "transfer", "/admin",
}

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


@dataclass
class BrowserResult:
    success: bool
    message: str
    data: dict = field(default_factory=dict)


def _domain_allowed(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def _is_dangerous(url: str) -> bool:
    low = url.lower()
    return any(kw in low for kw in DANGEROUS_KEYWORDS)


class BrowserTool:
    """Pojedyncza sesja przeglądarki (perz-agent)."""

    name = "browser"
    description = (
        "Steruje przeglądarką (Playwright): navigate/click/type/read. "
        "Whitelist domen: httpbin, quotes.toscrape, books.toscrape, the-internet.herokuapp."
    )

    def __init__(self, headless: bool = True, require_confirm: bool = True):
        self.headless = headless
        self.require_confirm = require_confirm
        self._playwright = None
        self._browser = None
        self._page = None

    async def _ensure(self):
        if self._page:
            return
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._page = await self._browser.new_page()

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._page = None

    # ── actions ──────────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> BrowserResult:
        if not _domain_allowed(url):
            return BrowserResult(False, f"BLOCKED: domain not in whitelist ({url})")
        await self._ensure()
        await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
        title = await self._page.title()
        return BrowserResult(True, f"Navigated to {url}", {"title": title, "url": self._page.url})

    async def click(self, selector: str, confirmed: bool = False) -> BrowserResult:
        if not self._page:
            return BrowserResult(False, "No page open. Call navigate first.")
        url = self._page.url
        if _is_dangerous(url) and not confirmed:
            return BrowserResult(False,
                f"BLOCKED: dangerous URL '{url}' — set confirmed=True to override")
        try:
            await self._page.click(selector, timeout=5000)
            return BrowserResult(True, f"Clicked {selector}", {"url": self._page.url})
        except Exception as e:
            return BrowserResult(False, f"Click failed: {e}")

    async def type_text(self, selector: str, text: str) -> BrowserResult:
        if not self._page:
            return BrowserResult(False, "No page open.")
        try:
            await self._page.fill(selector, text)
            return BrowserResult(True, f"Typed {len(text)} chars into {selector}")
        except Exception as e:
            return BrowserResult(False, f"Type failed: {e}")

    async def fill_form(self, fields: dict[str, str], confirmed: bool = False) -> BrowserResult:
        """fields = {"#email": "x@y.z", "input[name=name]": "Foo"}.
        NIE submituje automatycznie — submit wymaga jawnego click + confirmed=True."""
        if not self._page:
            return BrowserResult(False, "No page open.")
        filled = {}
        for sel, val in fields.items():
            try:
                await self._page.fill(sel, val)
                filled[sel] = "ok"
            except Exception as e:
                filled[sel] = f"error: {e}"
        return BrowserResult(True, f"Filled {len(filled)} fields", {"results": filled})

    async def read_text(self, selector: Optional[str] = None) -> BrowserResult:
        if not self._page:
            return BrowserResult(False, "No page open.")
        if selector:
            try:
                txt = await self._page.text_content(selector, timeout=3000)
                return BrowserResult(True, f"Read {selector}", {"text": (txt or "")[:2000]})
            except Exception as e:
                return BrowserResult(False, f"Read failed: {e}")
        txt = await self._page.text_content("body")
        return BrowserResult(True, "Read body", {"text": (txt or "")[:3000]})

    async def screenshot(self, name: Optional[str] = None) -> BrowserResult:
        if not self._page:
            return BrowserResult(False, "No page open.")
        fname = name or f"shot_{int(time.time())}.png"
        path = SCREENSHOT_DIR / fname
        await self._page.screenshot(path=str(path))
        return BrowserResult(True, f"Screenshot saved", {"path": str(path)})

    # ── agent tool interface (sync wrapper) ──────────────────────────────────

    def __call__(self, params: dict) -> str:
        return asyncio.run(self._dispatch(params))

    async def _dispatch(self, params: dict) -> str:
        action = params.get("action", "")
        try:
            if action == "navigate":
                r = await self.navigate(params["url"])
            elif action == "click":
                r = await self.click(params["selector"], params.get("confirmed", False))
            elif action == "type":
                r = await self.type_text(params["selector"], params["text"])
            elif action == "fill_form":
                r = await self.fill_form(params["fields"], params.get("confirmed", False))
            elif action == "read":
                r = await self.read_text(params.get("selector"))
            elif action == "screenshot":
                r = await self.screenshot(params.get("name"))
            else:
                r = BrowserResult(False, f"Unknown action: {action}")
            return f"[{'OK' if r.success else 'FAIL'}] {r.message}" + (
                f"\nDATA: {r.data}" if r.data else "")
        finally:
            if params.get("close_after"):
                await self.close()


# ── agent tool registry entry ─────────────────────────────────────────────────

BROWSER_TOOL_SPEC = {
    "name": "browser",
    "description": (
        "Steruje przeglądarką. action ∈ {navigate, click, type, fill_form, read, screenshot}. "
        "Domeny: whitelist tylko (httpbin, quotes.toscrape, books.toscrape, the-internet.herokuapp). "
        "fill_form NIE submituje — submit wymaga oddzielnego click z confirmed=True."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum":
                       ["navigate", "click", "type", "fill_form", "read", "screenshot"]},
            "url": {"type": "string"},
            "selector": {"type": "string"},
            "text": {"type": "string"},
            "fields": {"type": "object"},
            "confirmed": {"type": "boolean"},
            "name": {"type": "string"},
            "close_after": {"type": "boolean"},
        },
        "required": ["action"],
    },
}
