#!/usr/bin/env python3
"""
Smoke test MCP — weryfikuje działanie klienta i serwera.

Test 1 (serwer): uruchamia server.py w trybie stdio jako subprocess,
                 wywołuje tools/list i tools/call (web_search).

Test 2 (klient): używa MCPClient do połączenia z tym samym serwerem.

Uruchomienie:
    python3 ~/qwen-agent/mcp/smoke_test.py
    python3 ~/qwen-agent/mcp/smoke_test.py --verbose
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = ""):
    icon = "✓" if passed else "✗"
    RESULTS.append((name, passed, detail))
    print(f"  [{icon}] {name}", end="")
    if detail:
        print(f": {detail}", end="")
    print()


# ── TEST 1: raw JSON-RPC do serwera przez subprocess ─────────────────────────

def test_server_raw():
    print("\n=== Test 1: raw JSON-RPC (stdio) ===")
    server_script = Path(__file__).parent / "server.py"
    if not server_script.exists():
        check("server.py istnieje", False, f"Nie znaleziono: {server_script}")
        return

    check("server.py istnieje", True)

    proc = subprocess.Popen(
        [sys.executable, str(server_script), "--mode", "stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def rpc(method, params=None):
        msg = {"jsonrpc": "2.0", "id": rpc.counter, "method": method, "params": params or {}}
        rpc.counter += 1
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            line = proc.stdout.readline().strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
                if resp.get("id") == msg["id"]:
                    return resp
            except json.JSONDecodeError:
                continue
        return None
    rpc.counter = 1

    try:
        # initialize
        resp = rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "1.0"},
        })
        check("initialize OK", resp is not None and "result" in resp,
              str(resp.get("result", {}).get("serverInfo", "?")))

        # tools/list
        resp = rpc("tools/list")
        tools = resp.get("result", {}).get("tools", []) if resp else []
        check("tools/list OK", len(tools) > 0, f"{len(tools)} narzędzi")
        expected = {"web_search", "vision_ocr", "agent_task", "gig_finder", "rag_query", "scraper_fetch"}
        found = {t["name"] for t in tools}
        missing = expected - found
        check("wszystkie narzędzia obecne", len(missing) == 0,
              f"brakuje: {missing}" if missing else "OK")

        # tools/call web_search (SearxNG może nie działać, liczymy tylko format)
        resp = rpc("tools/call", {"name": "web_search", "arguments": {"query": "test MCP smoke"}})
        check("tools/call web_search — odpowiedź", resp is not None, "")
        if resp and "result" in resp:
            content = resp["result"].get("content", [])
            check("tools/call — content list", isinstance(content, list), f"{len(content)} elementów")
        elif resp and "error" in resp:
            # Błąd narzędzia (SearxNG offline) jest OK — ważny format
            check("tools/call — error format OK", True, f"narzędzie zwróciło błąd (oczekiwane bez SearxNG)")

    finally:
        proc.stdin.close()
        proc.wait(timeout=5)


# ── TEST 2: MCPClient wysokiego poziomu ───────────────────────────────────────

def test_mcp_client():
    print("\n=== Test 2: MCPClient (high-level API) ===")
    try:
        from mcp.client import MCPClient
        check("import MCPClient", True)
    except ImportError as e:
        check("import MCPClient", False, str(e))
        return

    server_script = str(Path(__file__).parent / "server.py")

    # Tymczasowa konfiguracja inline (nie z YAML) — nadpisujemy connect
    import types

    client = MCPClient.__new__(MCPClient)
    client.server_name = "test_local"
    client._config = {
        "transport": "stdio",
        "command": sys.executable,
        "args": [server_script, "--mode", "stdio"],
    }
    client._transport = None

    try:
        client.connect()
        check("connect()", client._transport is not None)

        tools = client.list_tools()
        check("list_tools()", len(tools) > 0, f"{len(tools)} narzędzi")

        agent_specs = client.as_agent_tools()
        check("as_agent_tools()", len(agent_specs) > 0, f"{len(agent_specs)} specs")

        # Sprawdź że każda spec ma wymagane pola i handler
        all_valid = all(
            "name" in s and "description" in s and "handler" in s and callable(s["handler"])
            for s in agent_specs
        )
        check("tool_spec format OK", all_valid)

        # Sprawdź namespace
        names = [s["name"] for s in agent_specs]
        namespaced = all(s.startswith("test_local__") for s in names)
        check("namespace '<server>__<tool>'", namespaced, f"np. {names[0] if names else '?'}")

        # Wywołaj narzędzie przez agent spec handler (web_search)
        ws_spec = next((s for s in agent_specs if s["name"].endswith("__web_search")), None)
        if ws_spec:
            result = ws_spec["handler"]({"query": "MCP smoke test", "max_results": 1})
            check("handler web_search wywołany", isinstance(result, str), f"{len(result)} znaków")

    except Exception as e:
        check("MCPClient test", False, str(e))
    finally:
        client.disconnect()


# ── PODSUMOWANIE ──────────────────────────────────────────────────────────────

def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    print("=" * 60)
    print("  MCP SMOKE TEST — qwen-agent v2")
    print("=" * 60)

    test_server_raw()
    test_mcp_client()

    print("\n── Podsumowanie ─────────────────────────────────────────")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    for name, ok, detail in RESULTS:
        icon = "✓" if ok else "✗"
        detail_str = f" ({detail})" if detail else ""
        print(f"  [{icon}] {name}{detail_str}")

    print(f"\nWynik: {passed}/{total} testów przeszło")
    if passed == total:
        print("STATUS: ✓ SMOKE TEST PASS")
    else:
        print(f"STATUS: ✗ {total - passed} TESTÓW NIEUDANYCH")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
