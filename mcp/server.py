#!/usr/bin/env python3
"""
MCP Server — wystawia narzędzia qwen-agent jako serwer MCP.

Narzędzia wystawiane:
  web_search    — wyszukiwanie przez lokalny SearxNG
  vision_ocr    — opis obrazu przez Ollama/llava
  agent_task    — uruchomienie zadania przez orchestrator
  gig_finder    — skanowanie ogłoszeń freelancingowych
  rag_query     — zapytanie do lokalnego RAG (qwen-rag)
  scraper_fetch — pobranie URL przez Playwright/httpx

Transporty:
  stdio (domyślny) — JSON-RPC 2.0 przez stdin/stdout
  http             — HTTP POST na /  (standardowy BaseHTTPRequestHandler)

Uruchomienie:
  python3 server.py --mode stdio          # stdio
  python3 server.py --mode http --port 8765  # HTTP
  python3 server.py --list               # wylistuj narzędzia

Podłączenie w Claude Desktop (claude_desktop_config.json):
  {
    "mcpServers": {
      "qwen-agent": {
        "command": "python3",
        "args": ["/Users/doomdoja/qwen-agent/mcp/server.py", "--mode", "stdio"]
      }
    }
  }

Podłączenie przez HTTP:
  Uruchom serwer z --mode http, ustaw url: http://localhost:8765 w servers.yaml.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

# Dodaj katalog główny do path żeby importy działały
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("qwen_agent.mcp.server")

MCP_PROTOCOL_VERSION = "2024-11-05"

# ── DEFINICJE NARZĘDZI ────────────────────────────────────────────────────────

def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


TOOL_DEFINITIONS: list[dict] = [
    _tool(
        "web_search",
        "Wyszukaj w sieci przez lokalny SearxNG. Zwraca tytuły, URL-e i snippety.",
        {
            "query": {"type": "string", "description": "Zapytanie wyszukiwania"},
            "max_results": {"type": "integer", "description": "Max wyników (domyślnie 5)", "default": 5},
        },
        required=["query"],
    ),
    _tool(
        "vision_ocr",
        "Opisz obraz / wykonaj OCR przez model llava (Ollama). Przekaż ścieżkę do pliku lub URL.",
        {
            "image": {"type": "string", "description": "Ścieżka do pliku obrazu lub URL"},
            "prompt": {"type": "string", "description": "Pytanie o obraz (domyślnie: 'Opisz ten obraz')"},
        },
        required=["image"],
    ),
    _tool(
        "agent_task",
        "Uruchom zadanie przez orchestrator multi-agentowy (planner → coder → verifier). "
        "Zwraca raport JSON z wynikiem.",
        {
            "task": {"type": "string", "description": "Opis zadania do wykonania"},
            "work_dir": {"type": "string", "description": "Katalog roboczy (opcjonalnie)"},
            "verify": {"type": "boolean", "description": "Uruchom verifier (domyślnie true)", "default": True},
        },
        required=["task"],
    ),
    _tool(
        "gig_finder",
        "Przeskanuj ogłoszenia freelancingowe (Upwork RSS, RemoteOK, Reddit, HN Hiring). "
        "Zwraca listę dopasowanych ofert.",
        {
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Słowa kluczowe do filtrowania (np. ['python', 'scraping'])",
            },
            "max_results": {"type": "integer", "description": "Max ogłoszeń (domyślnie 10)", "default": 10},
        },
        required=["keywords"],
    ),
    _tool(
        "rag_query",
        "Zapytaj lokalny RAG (qwen-rag / ChromaDB). Wymaga wcześniejszego zaindeksowania dokumentów.",
        {
            "question": {"type": "string", "description": "Pytanie do bazy wiedzy"},
            "collection": {"type": "string", "description": "Nazwa kolekcji (domyślnie: 'default')"},
        },
        required=["question"],
    ),
    _tool(
        "scraper_fetch",
        "Pobierz zawartość URL. Używa httpx (szybki) lub Playwright (dla JS-heavy stron).",
        {
            "url": {"type": "string", "description": "URL do pobrania"},
            "use_browser": {
                "type": "boolean",
                "description": "Użyj Playwright (dla JS-heavy stron, wolniejsze)",
                "default": False,
            },
            "extract_text": {
                "type": "boolean",
                "description": "Wyciągnij tylko tekst (bez HTML)",
                "default": True,
            },
        },
        required=["url"],
    ),
]

# Indeks po nazwie
_TOOL_INDEX: dict[str, dict] = {t["name"]: t for t in TOOL_DEFINITIONS}


# ── IMPLEMENTACJE NARZĘDZI ────────────────────────────────────────────────────

def _impl_web_search(args: dict) -> str:
    query = args.get("query", "")
    max_results = int(args.get("max_results", 5))
    try:
        from tools.web_search import web_search_formatted
        return web_search_formatted(query, max_results=max_results)
    except Exception as e:
        return f"web_search error: {e}"


def _impl_vision_ocr(args: dict) -> str:
    image = args.get("image", "")
    prompt = args.get("prompt", "Opisz ten obraz szczegółowo.")
    try:
        from core.llm_client import get_llm_client
        llm = get_llm_client()
        return llm.vision_generate(image, prompt)
    except Exception as e:
        return f"vision_ocr error: {e}"


def _impl_agent_task(args: dict) -> str:
    task = args.get("task", "")
    work_dir = args.get("work_dir", "")
    verify = args.get("verify", True)
    try:
        import subprocess
        cmd = [sys.executable, str(_ROOT / "multiagent" / "orchestrator.py"), task]
        if work_dir:
            cmd += ["--work-dir", work_dir]
        if verify:
            cmd += ["--verify"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        return output[-3000:] if len(output) > 3000 else output
    except Exception as e:
        return f"agent_task error: {e}"


def _impl_gig_finder(args: dict) -> str:
    keywords = args.get("keywords", [])
    max_results = int(args.get("max_results", 10))
    try:
        sys.path.insert(0, str(_ROOT / "gig-finder"))
        from sources.upwork_rss import UpworkRSS
        from sources.remoteok import RemoteOK
        results = []
        for source_cls in [UpworkRSS, RemoteOK]:
            try:
                source = source_cls()
                gigs = source.fetch()
                for g in gigs:
                    title = (g.get("title") or "").lower()
                    if any(kw.lower() in title for kw in keywords):
                        results.append(f"[{source_cls.__name__}] {g.get('title')} — {g.get('url','')}")
            except Exception:
                continue
        if not results:
            return f"Nie znaleziono ogłoszeń dla: {keywords}"
        return "\n".join(results[:max_results])
    except Exception as e:
        return f"gig_finder error: {e}"


def _impl_rag_query(args: dict) -> str:
    question = args.get("question", "")
    collection = args.get("collection", "default")
    rag_query_script = Path.home() / "qwen-rag" / "query.py"
    if not rag_query_script.exists():
        return "RAG nie zainstalowany. Uruchom: python3 ~/qwen-rag/ingest.py <plik>"
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(rag_query_script), question, "--collection", collection],
            capture_output=True, text=True, timeout=60
        )
        return (result.stdout + result.stderr).strip() or "Brak wyników RAG."
    except Exception as e:
        return f"rag_query error: {e}"


def _impl_scraper_fetch(args: dict) -> str:
    url = args.get("url", "")
    use_browser = args.get("use_browser", False)
    extract_text = args.get("extract_text", True)
    try:
        import httpx, re as _re
        resp = httpx.get(url, follow_redirects=True, timeout=15,
                         headers={"User-Agent": "qwen-agent/2.0"})
        resp.raise_for_status()
        content = resp.text
        if extract_text:
            # Usuń tagi HTML
            content = _re.sub(r'<[^>]+>', ' ', content)
            content = _re.sub(r'\s+', ' ', content).strip()
        return content[:5000]
    except Exception as e:
        return f"scraper_fetch error: {e}"


_HANDLERS: dict[str, Callable[[dict], str]] = {
    "web_search": _impl_web_search,
    "vision_ocr": _impl_vision_ocr,
    "agent_task": _impl_agent_task,
    "gig_finder": _impl_gig_finder,
    "rag_query": _impl_rag_query,
    "scraper_fetch": _impl_scraper_fetch,
}


# ── PROTOKÓŁ MCP ──────────────────────────────────────────────────────────────

class MCPServer:
    """Obsługuje żądania JSON-RPC 2.0 według protokołu MCP."""

    def handle(self, request: dict) -> dict | None:
        """Przetwórz żądanie, zwróć odpowiedź lub None (dla notyfikacji)."""
        method = request.get("method", "")
        params = request.get("params") or {}
        req_id = request.get("id")

        # Notyfikacje (brak id) — nie wymagają odpowiedzi
        if req_id is None and method.startswith("notifications/"):
            return None

        try:
            result = self._dispatch(method, params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except NotImplementedError:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            }
        except Exception as e:
            logger.error(f"Error handling {method}: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    def _dispatch(self, method: str, params: dict) -> Any:
        if method == "initialize":
            return {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "qwen-agent-mcp", "version": "2.0"},
            }
        elif method == "tools/list":
            return {"tools": TOOL_DEFINITIONS}
        elif method == "tools/call":
            return self._call_tool(params)
        elif method == "ping":
            return {}
        else:
            raise NotImplementedError(method)

    def _call_tool(self, params: dict) -> dict:
        name = params.get("name", "")
        arguments = params.get("arguments") or {}

        if name not in _HANDLERS:
            known = list(_HANDLERS.keys())
            raise ValueError(f"Unknown tool: '{name}'. Known: {known}")

        logger.info(f"[MCP] Calling tool: {name}({list(arguments.keys())})")
        text = _HANDLERS[name](arguments)
        return {"content": [{"type": "text", "text": text}]}


# ── TRYB STDIO ────────────────────────────────────────────────────────────────

def run_stdio(server: MCPServer):
    """Nasłuchuj na stdin, odpowiadaj na stdout (JSON-RPC line-delimited)."""
    logger.info("[MCP Server] Starting stdio mode")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}}
            print(json.dumps(resp), flush=True)
            continue

        response = server.handle(request)
        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)


# ── TRYB HTTP ─────────────────────────────────────────────────────────────────

def run_http(server: MCPServer, host: str = "localhost", port: int = 8765):
    """HTTP POST na / — JSON-RPC 2.0."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                request = json.loads(body)
                response = server.handle(request) or {}
            except json.JSONDecodeError as e:
                response = {"jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": f"Parse error: {e}"}}

            payload = json.dumps(response, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            # Prosty health-check
            body = json.dumps({"status": "ok", "server": "qwen-agent-mcp"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            logger.debug(f"HTTP {fmt % args}")

    httpd = HTTPServer((host, port), Handler)
    logger.info(f"[MCP Server] HTTP mode: http://{host}:{port}/")
    print(f"[MCP Server] Nasłuchuję: http://{host}:{port}/", flush=True)
    httpd.serve_forever()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    parser = argparse.ArgumentParser(description="qwen-agent MCP Server")
    parser.add_argument("--mode", choices=["stdio", "http"], default="stdio",
                        help="Transport: stdio (domyślnie) lub http")
    parser.add_argument("--host", default="localhost", help="Host dla HTTP (domyślnie: localhost)")
    parser.add_argument("--port", type=int, default=8765, help="Port dla HTTP (domyślnie: 8765)")
    parser.add_argument("--list", action="store_true", help="Wylistuj dostępne narzędzia i wyjdź")
    args = parser.parse_args()

    if args.list:
        print(f"qwen-agent MCP Server — {len(TOOL_DEFINITIONS)} narzędzi:\n")
        for t in TOOL_DEFINITIONS:
            schema = t["inputSchema"]
            req = schema.get("required", [])
            props = list(schema.get("properties", {}).keys())
            print(f"  {t['name']:20s} — {t['description'][:60]}")
            print(f"  {'':20s}   params: {props}  required: {req}\n")
        sys.exit(0)

    server = MCPServer()

    if args.mode == "stdio":
        run_stdio(server)
    else:
        run_http(server, host=args.host, port=args.port)
