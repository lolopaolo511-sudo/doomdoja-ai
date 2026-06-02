#!/usr/bin/env python3
"""
MCP Client — łączy agenta z zewnętrznymi serwerami MCP.

Obsługiwane transporty:
  stdio — uruchamia serwer jako subprocess, JSON-RPC przez stdin/stdout
  http  — wywołania przez HTTP POST (JSON-RPC 2.0)

Konfiguracja serwerów: mcp/servers.yaml

Przykład użycia:
    from mcp.client import MCPClient, load_mcp_tools

    # Załaduj narzędzia z wszystkich włączonych serwerów
    tools = load_mcp_tools()          # lista tool_spec gotowa dla ReAct agenta

    # Albo ręcznie:
    with MCPClient("local_qwen") as client:
        tools = client.list_tools()
        result = client.call_tool("web_search", {"query": "Python asyncio"})
        print(result)
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml

logger = logging.getLogger("qwen_agent.mcp.client")

SERVERS_YAML = Path(__file__).parent / "servers.yaml"
MCP_PROTOCOL_VERSION = "2024-11-05"


# ── TRANSPORTY ────────────────────────────────────────────────────────────────

class StdioTransport:
    """JSON-RPC 2.0 przez stdin/stdout (subprocess)."""

    def __init__(self, command: list[str]):
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()
        self._id = 0
        self._initialized = False

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send_raw(self, method: str, params: dict) -> dict:
        req_id = self._next_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        with self._lock:
            line = json.dumps(msg, ensure_ascii=False) + "\n"
            self._proc.stdin.write(line)
            self._proc.stdin.flush()

            # Czytaj odpowiedzi aż znajdziemy tę z pasującym id
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                resp_line = self._proc.stdout.readline()
                if not resp_line:
                    raise ConnectionError("MCP server closed connection (EOF on stdout)")
                resp_line = resp_line.strip()
                if not resp_line:
                    continue
                try:
                    resp = json.loads(resp_line)
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON line from MCP server: {resp_line[:200]}")
                    continue

                if resp.get("id") == req_id:
                    if "error" in resp:
                        err = resp["error"]
                        raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
                    return resp.get("result") or {}
            raise TimeoutError(f"MCP server did not respond to '{method}' within 30s")

    def initialize(self) -> dict:
        result = self._send_raw("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "qwen-agent", "version": "2.0"},
        })
        # Send initialized notification (no response expected)
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        self._proc.stdin.write(json.dumps(notif) + "\n")
        self._proc.stdin.flush()
        self._initialized = True
        return result

    def list_tools(self) -> list[dict]:
        result = self._send_raw("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> list[dict]:
        result = self._send_raw("tools/call", {"name": name, "arguments": arguments})
        return result.get("content", [])

    def close(self):
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()


class HttpTransport:
    """JSON-RPC 2.0 przez HTTP POST."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self._client = httpx.Client(timeout=30)
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send_raw(self, method: str, params: dict) -> dict:
        req_id = self._next_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        resp = self._client.post(self.url, json=msg)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
        return data.get("result") or {}

    def initialize(self) -> dict:
        return self._send_raw("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "qwen-agent", "version": "2.0"},
        })

    def list_tools(self) -> list[dict]:
        result = self._send_raw("tools/list", {})
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> list[dict]:
        result = self._send_raw("tools/call", {"name": name, "arguments": arguments})
        return result.get("content", [])

    def close(self):
        self._client.close()


# ── GŁÓWNY KLIENT ─────────────────────────────────────────────────────────────

class MCPClient:
    """
    Klient MCP — łączy się z jednym serwerem MCP i udostępnia jego narzędzia.

    Użycie:
        with MCPClient("local_qwen") as client:
            tools = client.list_tools()
            result = client.call_tool("web_search", {"query": "..."})
    """

    def __init__(self, server_name: str, servers_yaml: Path = SERVERS_YAML):
        self.server_name = server_name
        self._config = self._load_server_config(server_name, servers_yaml)
        self._transport: Optional[StdioTransport | HttpTransport] = None

    @staticmethod
    def _load_server_config(name: str, yaml_path: Path) -> dict:
        if not yaml_path.exists():
            raise FileNotFoundError(f"servers.yaml not found: {yaml_path}")
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        servers = data.get("servers", {})
        if name not in servers:
            available = list(servers.keys())
            raise KeyError(f"MCP server '{name}' not found in {yaml_path}. Available: {available}")
        return servers[name]

    def connect(self):
        """Nawiąż połączenie z serwerem."""
        transport = self._config.get("transport", "stdio")
        if transport == "stdio":
            command_raw = self._config.get("command", "python3")
            args = self._config.get("args", [])
            command = [command_raw] + [str(a) for a in args]
            logger.info(f"[MCP] Connecting stdio: {' '.join(command[:3])}...")
            self._transport = StdioTransport(command)
        elif transport in ("http", "sse"):
            url = self._config.get("url", "http://localhost:8765")
            logger.info(f"[MCP] Connecting http: {url}")
            self._transport = HttpTransport(url)
        else:
            raise ValueError(f"Unknown MCP transport: {transport}")

        try:
            info = self._transport.initialize()
            logger.info(f"[MCP] Connected to '{self.server_name}': {info.get('serverInfo', {})}")
        except Exception as e:
            logger.warning(f"[MCP] initialize() failed (non-fatal): {e}")

        return self

    def disconnect(self):
        if self._transport:
            self._transport.close()
            self._transport = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.disconnect()

    def list_tools(self) -> list[dict]:
        """Zwróć listę narzędzi serwera w formacie MCP."""
        if not self._transport:
            raise RuntimeError("Not connected. Use connect() or 'with' statement.")
        return self._transport.list_tools()

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Wywołaj narzędzie i zwróć wynik jako string."""
        if not self._transport:
            raise RuntimeError("Not connected.")
        content = self._transport.call_tool(tool_name, arguments)
        # Złącz wszystkie elementy tekstowe
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                else:
                    parts.append(json.dumps(item))
            else:
                parts.append(str(item))
        return "\n".join(parts) if parts else ""

    def as_agent_tools(self) -> list[dict]:
        """
        Konwertuj narzędzia MCP na format tool_spec agenta ReAct.

        Każde narzędzie dostaje namespace: "<server_name>__<tool_name>".
        Może być bezpośrednio dodane do rejestru narzędzi agenta.
        """
        tools_raw = self.list_tools()
        specs = []
        for tool in tools_raw:
            original_name = tool["name"]
            namespaced_name = f"{self.server_name}__{original_name}"
            transport = self._transport  # capture for closure

            def make_handler(t=original_name, tr=transport):
                def handler(params: dict) -> str:
                    content = tr.call_tool(t, params)
                    parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            parts.append(item.get("text", ""))
                        else:
                            parts.append(str(item))
                    return "\n".join(parts) if parts else ""
                return handler

            spec = {
                "name": namespaced_name,
                "description": f"[MCP:{self.server_name}] {tool.get('description', '')}",
                "parameters": tool.get("inputSchema", {
                    "type": "object",
                    "properties": {},
                    "required": [],
                }),
                "handler": make_handler(),
            }
            specs.append(spec)
            logger.debug(f"[MCP] Registered tool: {namespaced_name}")
        return specs


# ── POMOCNIK WYSOKIEGO POZIOMU ────────────────────────────────────────────────

def load_mcp_tools(
    servers_yaml: Path = SERVERS_YAML,
    only_enabled: bool = True,
) -> list[dict]:
    """
    Załaduj narzędzia ze wszystkich włączonych serwerów MCP.

    Zwraca listę tool_spec gotową do wpięcia w rejestr narzędzi agenta.
    Połączenia są utrzymywane — zwróć uwagę na zarządzanie cyklem życia.

    Użycie w agencie ReAct:
        mcp_tools = load_mcp_tools()
        all_tools = agent_tools + mcp_tools
    """
    if not servers_yaml.exists():
        logger.warning(f"[MCP] servers.yaml not found: {servers_yaml}")
        return []

    data = yaml.safe_load(servers_yaml.read_text(encoding="utf-8"))
    servers = data.get("servers", {})
    all_tools: list[dict] = []

    for name, cfg in servers.items():
        if only_enabled and not cfg.get("enabled", False):
            logger.debug(f"[MCP] Skipping disabled server: {name}")
            continue

        requires = cfg.get("requires")
        if requires == "node":
            import shutil
            if not shutil.which("node"):
                logger.warning(f"[MCP] Skipping '{name}': requires node (not found in PATH)")
                continue

        try:
            client = MCPClient(name, servers_yaml)
            client.connect()
            tools = client.as_agent_tools()
            all_tools.extend(tools)
            logger.info(f"[MCP] Loaded {len(tools)} tools from '{name}'")
        except Exception as e:
            logger.error(f"[MCP] Failed to load tools from '{name}': {e}")

    logger.info(f"[MCP] Total MCP tools loaded: {len(all_tools)}")
    return all_tools


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="MCP Client CLI")
    parser.add_argument("--server", default="local_qwen", help="Nazwa serwera z servers.yaml")
    parser.add_argument("--list", action="store_true", help="Listuj narzędzia serwera")
    parser.add_argument("--call", help="Nazwa narzędzia do wywołania")
    parser.add_argument("--args", default="{}", help="JSON argumenty dla --call")
    args = parser.parse_args()

    with MCPClient(args.server) as client:
        if args.list or not args.call:
            tools = client.list_tools()
            print(f"\nNarzędzia serwera '{args.server}' ({len(tools)}):")
            for t in tools:
                print(f"  {t['name']:30s} — {t.get('description', '')[:60]}")
        if args.call:
            call_args = json.loads(args.args)
            print(f"\nWywołuję: {args.call}({call_args})")
            result = client.call_tool(args.call, call_args)
            print(f"Wynik:\n{result}")
