"""
computer_use/register.py — wepnij narzędzia browser+desktop do rejestru agenta.

Użycie:
    from computer_use.register import register_computer_use_tools
    register_computer_use_tools()  # dodaje narzędzia do TOOL_REGISTRY

Po rejestracji agent może używać: navigate, read_page, click, type_text,
extract, screenshot, desktop_screenshot jako normalnych ReAct tools.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Upewnij się że katalog projektu jest na ścieżce
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def register_computer_use_tools(registry: list | None = None) -> bool:
    """
    Rejestruje narzędzia computer_use w TOOL_REGISTRY.

    Args:
        registry: lista narzędzi (domyślnie próbuje multiagent/orchestrator.TOOL_REGISTRY)

    Returns:
        True jeśli sukces, False jeśli rejestr niedostępny (nie przerywa pracy agenta).
    """
    from .browser_agent import BrowserAgent, COMPUTER_USE_TOOLS
    from .desktop import DESKTOP_TOOL_SPEC, desktop_screenshot_tool

    # Zbuduj listę do zarejestrowania
    browser_session = BrowserAgent(headless=True)

    tools_to_register = []
    for spec in COMPUTER_USE_TOOLS:
        action_name = spec["name"]

        def make_handler(action: str, session: BrowserAgent):
            def handler(params: dict) -> str:
                params = dict(params)
                params["action"] = action
                return session(params)
            return handler

        entry = dict(spec)
        entry["handler"] = make_handler(action_name, browser_session)
        tools_to_register.append(entry)

    # Desktop screenshot
    desktop_entry = dict(DESKTOP_TOOL_SPEC)
    desktop_entry["handler"] = desktop_screenshot_tool
    tools_to_register.append(desktop_entry)

    # Spróbuj dodać do podanego rejestru lub globalnego
    if registry is not None:
        _add_tools(registry, tools_to_register)
        return True

    # Próbuj multiagent TOOL_REGISTRY
    try:
        sys.path.insert(0, str(_ROOT / "multiagent"))
        from agent_runner import TOOL_REGISTRY as global_registry
        _add_tools(global_registry, tools_to_register)
        print(f"[computer_use] Zarejestrowano {len(tools_to_register)} narzędzi "
              f"({len(global_registry)} razem)")
        return True
    except ImportError:
        pass

    # Próbuj qwen-scraper tools
    try:
        sys.path.insert(0, str(Path.home() / "qwen-scraper"))
        from agent.tools import TOOL_REGISTRY as scraper_registry
        _add_tools(scraper_registry, tools_to_register)
        print(f"[computer_use] Zarejestrowano {len(tools_to_register)} narzędzi "
              f"w qwen-scraper ({len(scraper_registry)} razem)")
        return True
    except ImportError:
        pass

    print("[computer_use] WARN: nie znaleziono TOOL_REGISTRY — narzędzia nie zarejestrowane")
    print("[computer_use] Użyj: register_computer_use_tools(moja_lista_narzedzi)")
    return False


def _add_tools(registry: list, tools: list) -> None:
    existing_names = {t.get("name") for t in registry}
    added = 0
    for tool in tools:
        if tool["name"] not in existing_names:
            registry.append(tool)
            existing_names.add(tool["name"])
            added += 1
        else:
            print(f"[computer_use] '{tool['name']}' już zarejestrowany — pomijam")
    if added:
        print(f"[computer_use] Dodano {added} narzędzi: "
              f"{[t['name'] for t in tools[:added]]}")


if __name__ == "__main__":
    print("=== Test rejestracji computer_use tools ===")
    test_registry: list = []
    register_computer_use_tools(test_registry)
    print(f"Zarejestrowane narzędzia ({len(test_registry)}):")
    for t in test_registry:
        print(f"  • {t['name']}: {t['description'][:70]}")
