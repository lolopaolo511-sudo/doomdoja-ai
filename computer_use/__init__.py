"""computer_use — ReAct narzędzia browser + desktop screenshot."""
from .browser_agent import BrowserAgent, BrowserResult, COMPUTER_USE_TOOLS
from .desktop import desktop_screenshot
from .register import register_computer_use_tools

__all__ = [
    "BrowserAgent",
    "BrowserResult",
    "COMPUTER_USE_TOOLS",
    "desktop_screenshot",
    "register_computer_use_tools",
]
