#!/usr/bin/env python3
"""
Demo: agent przegląda quotes.toscrape.com + wypełnia formularz na herokuapp.
Pokazuje: navigate → read → screenshot → fill_form (bez submit).
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser_tool import BrowserTool


async def demo_quotes():
    print("\n=== DEMO 1: scraping cytatów z quotes.toscrape.com ===")
    bt = BrowserTool(headless=True)
    r = await bt.navigate("https://quotes.toscrape.com")
    print(f"  navigate: {r.message} | title={r.data.get('title')}")

    r = await bt.read_text(".quote .text")
    print(f"  read first quote: {r.data.get('text', '')[:120]}")

    r = await bt.screenshot("quotes_home.png")
    print(f"  screenshot: {r.message} → {r.data.get('path')}")

    # navigate to login page (no real auth, just a form on the same site)
    r = await bt.navigate("https://quotes.toscrape.com/login")
    print(f"  navigate login: {r.message}")

    r = await bt.fill_form({
        "input[name=username]": "demo_user",
        "input[name=password]": "demo_pass",
    })
    print(f"  fill_form: {r.message}")
    print(f"  (Note: NIE submitujemy — confirmed=False blocked by default)")

    await bt.close()


async def demo_httpbin_form():
    print("\n=== DEMO 2: formularz na httpbin.org/forms/post ===")
    bt = BrowserTool(headless=True)
    r = await bt.navigate("https://httpbin.org/forms/post")
    print(f"  navigate: {r.message}")

    r = await bt.fill_form({
        "input[name=custname]": "Jan Kowalski",
        "input[name=custtel]": "+48 600 000 000",
        "input[name=custemail]": "jan@example.com",
    })
    print(f"  fill_form: {r.message}")

    r = await bt.screenshot("httpbin_form_filled.png")
    print(f"  screenshot: {r.data.get('path')}")

    await bt.close()


async def demo_safety():
    print("\n=== DEMO 3: bezpieczniki ===")
    bt = BrowserTool(headless=True)
    r = await bt.navigate("https://malicious-domain.com")
    print(f"  Blocked domain: {r.message}")

    r = await bt.navigate("https://example.com")
    print(f"  Allowed: {r.message}")

    await bt.close()


async def main():
    await demo_quotes()
    await demo_httpbin_form()
    await demo_safety()
    print("\n=== KONIEC DEMO ===")


if __name__ == "__main__":
    asyncio.run(main())
