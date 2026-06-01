"""
Wepnij BrowserTool do rejestru narzędzi qwen-scraper.agent.tools.

Użycie:
    from qwen_agent.browser.register import register_browser
    register_browser()  # dodaje 'browser' tool do TOOL_REGISTRY
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path.home() / "qwen-scraper"))

from browser_tool import BROWSER_TOOL_SPEC, BrowserTool


def register_browser():
    try:
        from agent.tools import TOOL_REGISTRY
    except ImportError as e:
        print(f"[register] qwen-scraper agent.tools nie dostępny: {e}")
        return False

    if any(t["name"] == "browser" for t in TOOL_REGISTRY):
        print("[register] 'browser' już zarejestrowany")
        return True

    bt = BrowserTool(headless=True)
    spec = dict(BROWSER_TOOL_SPEC)
    spec["handler"] = bt
    TOOL_REGISTRY.append(spec)
    print(f"[register] OK — 'browser' dodany ({len(TOOL_REGISTRY)} narzędzi razem)")
    return True


if __name__ == "__main__":
    register_browser()
    from agent.tools import TOOL_REGISTRY
    for t in TOOL_REGISTRY:
        print(f"  • {t['name']}: {t['description'][:80]}")
