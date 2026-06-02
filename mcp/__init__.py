"""
qwen-agent MCP layer — klient i serwer Model Context Protocol.

Eksportuje:
    MCPClient      — łączy agenta z zewnętrznymi serwerami MCP
    MCPServer      — wystawia narzędzia agenta jako serwer MCP
    load_mcp_tools — ładuje narzędzia z serwerów do rejestru agenta
"""

from .client import MCPClient, load_mcp_tools
from .server import MCPServer

__all__ = ["MCPClient", "MCPServer", "load_mcp_tools"]
