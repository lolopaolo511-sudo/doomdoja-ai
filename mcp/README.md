# MCP Layer — qwen-agent v2

Warstwa MCP (Model Context Protocol) umożliwia agentowi:
1. **Klientowi** łączyć się z zewnętrznymi serwerami MCP i używać ich narzędzi w pętli ReAct
2. **Serwerowi** wystawiać własne narzędzia tak, żeby inne aplikacje/agenci mogli z nich korzystać

## Struktura

```
mcp/
├── __init__.py       — eksporty: MCPClient, MCPServer, load_mcp_tools
├── client.py         — klient MCP (stdio + HTTP)
├── server.py         — serwer MCP (stdio + HTTP)
├── servers.yaml      — konfiguracja serwerów MCP
├── smoke_test.py     — weryfikacja działania klienta i serwera
└── README.md         — ten plik
```

## Szybki start

### Uruchomienie serwera (stdio)

```bash
python3 ~/qwen-agent/mcp/server.py --mode stdio
```

### Uruchomienie serwera (HTTP)

```bash
python3 ~/qwen-agent/mcp/server.py --mode http --port 8765
```

### Lista narzędzi

```bash
python3 ~/qwen-agent/mcp/server.py --list
```

Wynik:
```
qwen-agent MCP Server — 6 narzędzi:

  web_search           — Wyszukaj w sieci przez lokalny SearxNG...
  vision_ocr           — Opisz obraz / wykonaj OCR przez model llava...
  agent_task           — Uruchom zadanie przez orchestrator multi-agentowy...
  gig_finder           — Przeskanuj ogłoszenia freelancingowe...
  rag_query            — Zapytaj lokalny RAG (qwen-rag)...
  scraper_fetch        — Pobierz zawartość URL...
```

### Wywołanie przez klienta CLI

```bash
# Listuj narzędzia
python3 ~/qwen-agent/mcp/client.py --server local_qwen --list

# Wywołaj narzędzie
python3 ~/qwen-agent/mcp/client.py --server local_qwen \
  --call web_search --args '{"query": "python async best practices"}'
```

### Załaduj narzędzia MCP w pętli ReAct agenta

```python
from mcp.client import load_mcp_tools

# Załaduj wszystkie włączone serwery z servers.yaml
mcp_tools = load_mcp_tools()

# Połącz z lokalnymi narzędziami agenta
all_tools = agent_native_tools + mcp_tools

# Uruchom ReAct z połączonymi narzędziami
run_react_agent(task, tools=all_tools)
```

Każde narzędzie MCP dostaje namespace `<server_name>__<tool_name>`, np. `local_qwen__web_search`.

### Smoke test

```bash
python3 ~/qwen-agent/mcp/smoke_test.py
python3 ~/qwen-agent/mcp/smoke_test.py --verbose
```

## Podłączenie do Claude Desktop

W `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qwen-agent": {
      "command": "python3",
      "args": ["/Users/doomdoja/qwen-agent/mcp/server.py", "--mode", "stdio"]
    }
  }
}
```

## Konfiguracja serwerów (servers.yaml)

Edytuj `mcp/servers.yaml` żeby włączyć/wyłączyć serwery lub dodać nowe:

```yaml
servers:
  local_qwen:
    transport: stdio
    command: python3
    args: [/Users/doomdoja/qwen-agent/mcp/server.py, --mode, stdio]
    enabled: true

  remote_custom:
    transport: http
    url: http://your-server:8765
    enabled: false
```

## Narzędzia wystawiane

| Narzędzie      | Opis                                        | Wymagania             |
|----------------|---------------------------------------------|-----------------------|
| `web_search`   | Wyszukiwanie przez SearxNG                  | Docker stack uruchomiony |
| `vision_ocr`   | Opis/OCR obrazu przez llava                 | Ollama + llava:7b     |
| `agent_task`   | Uruchomienie zadania przez orchestrator     | Ollama + deepseek     |
| `gig_finder`   | Skanowanie ogłoszeń freelancingowych        | Internet              |
| `rag_query`    | Zapytanie do RAG (ChromaDB/Qdrant)          | qwen-rag zainstalowany |
| `scraper_fetch`| Pobieranie stron WWW                        | Internet              |

## Protokół MCP

Implementacja zgodna z [Model Context Protocol](https://modelcontextprotocol.io/) v2024-11-05.
Obsługiwane metody: `initialize`, `tools/list`, `tools/call`, `ping`.
Transport: JSON-RPC 2.0 line-delimited (stdio) lub HTTP POST.
