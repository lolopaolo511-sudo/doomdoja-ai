#!/usr/bin/env python3
"""
computer_use/demo.py — demonstracja narzędzi browser + desktop.

Demo 1: quotes.toscrape.com — nawigacja + odczyt cytatów
Demo 2: httpbin.org/forms/post — nawigacja + wypełnienie formularza (BEZ submit)
Demo 3: desktop_screenshot() — zrzut ekranu pulpitu

Wymagania: playwright zainstalowany (`pip install playwright && playwright install chromium`)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from computer_use.browser_agent import BrowserAgent, BrowserResult
from computer_use.desktop import desktop_screenshot


async def demo_quotes():
    """Demo 1: nawigacja + odczyt + ekstrakcja cytatów."""
    print("\n── Demo 1: quotes.toscrape.com ──────────────────────────")
    agent = BrowserAgent(headless=True)
    try:
        # 1. Nawigacja
        r = await agent.navigate("http://quotes.toscrape.com")
        print(f"navigate → {r}")

        # 2. Odczyt całej strony
        r = await agent.read_page()
        print(f"read_page → {r.message}, {len(r.data.get('text', ''))} znaków")
        snippet = r.data.get("text", "")[:300].replace("\n", " ")
        print(f"  snippet: {snippet}...")

        # 3. Odczyt konkretnego elementu (pierwsze cytaty)
        r = await agent.read_page(".quote .text")
        print(f"read_page(.quote .text) → {r.message}")
        print(f"  pierwszy cytat: {r.data.get('text', '')[:120]}...")

        # 4. Screenshot
        r = await agent.screenshot("demo_quotes.png")
        print(f"screenshot → {r}")

    finally:
        await agent.close()


async def demo_httpbin_form():
    """Demo 2: wypełnienie formularza na httpbin BEZ submitu."""
    print("\n── Demo 2: httpbin.org/forms/post (wypełnienie bez submit) ──")
    agent = BrowserAgent(headless=True)
    try:
        # 1. Nawigacja do formularza
        r = await agent.navigate("https://httpbin.org/forms/post")
        print(f"navigate → {r}")

        # 2. Odczyt formularza
        r = await agent.read_page("form")
        print(f"read_page(form) → {r.message}")

        # 3. Wypełnienie pól (BEZ submit — bezpieczne)
        r = await agent.type_text("input[name=custname]", "Jan Kowalski")
        print(f"type_text(custname) → {r}")

        r = await agent.type_text("input[name=custtel]", "+48-123-456-789")
        print(f"type_text(custtel) → {r}")

        r = await agent.type_text("input[name=custemail]", "jan@example.com")
        print(f"type_text(custemail) → {r}")

        # 4. Próba kliknięcia submit BEZ confirm (powinno być BLOCKED)
        r = await agent.click("button[type=submit]")
        print(f"click(submit, confirm=False) → {r.message[:80]}")
        assert not r.success, "Oczekiwano BLOCKED!"
        print("  ✓ Submit zablokowany poprawnie (confirm=True wymagane)")

        # 5. Screenshot wypełnionego formularza
        r = await agent.screenshot("demo_form_filled.png")
        print(f"screenshot → {r}")

    finally:
        await agent.close()


def demo_desktop():
    """Demo 3: screenshot pulpitu (read-only)."""
    print("\n── Demo 3: desktop_screenshot() ─────────────────────────")
    result = desktop_screenshot("demo_desktop.png")
    if result["success"]:
        print(f"[OK] {result['message']}")
    else:
        print(f"[INFO] {result['message']} (to OK jeśli nie macOS)")


def demo_blocked_domain():
    """Demo 4: próba nawigacji do zablokowanej domeny."""
    print("\n── Demo 4: whitelist — zablokowana domena ───────────────")
    agent = BrowserAgent(headless=True)
    r = asyncio.run(agent.navigate("https://google.com"))
    print(f"navigate(google.com) → {r.message[:80]}")
    assert not r.success
    print("  ✓ Domena zablokowana poprawnie")


async def main():
    print("=" * 60)
    print("computer_use DEMO")
    print("=" * 60)

    # Demo 4 (sync, szybkie sprawdzenie) — bez Playwright
    demo_blocked_domain()

    # Demo 3 — desktop
    demo_desktop()

    # Demo 1 & 2 — wymagają Playwright
    try:
        await demo_quotes()
        await demo_httpbin_form()
        print("\n✓ Wszystkie dema przeszły pomyślnie.")
    except ImportError:
        print("\n[SKIP] playwright nie zainstalowany: pip install playwright && playwright install chromium")
    except Exception as e:
        print(f"\n[ERROR] Demo błąd: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
