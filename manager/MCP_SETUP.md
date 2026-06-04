# Podpięcie serwera MCP do Claude Desktop

## Status weryfikacji

Serwer MCP (`~/qwen-agent/mcp/server.py`) **DZIAŁA** w trybie stdio.

Weryfikacja (2026-06-04):
- `initialize` → `{"result": {"protocolVersion": "2024-11-05", "serverInfo": {"name": "qwen-agent-mcp"}}}` ✓
- `tools/list` → 6 narzędzi: `web_search`, `vision_ocr`, `agent_task`, `gig_finder`, `rag_query`, `scraper_fetch` ✓

---

## Plik config na macOS

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Plik **już istnieje** w Twoim systemie. Nie ma jeszcze klucza `mcpServers`.

---

## Co musisz zrobić sam (1 krok)

### Krok 1 — Dodaj klucz `mcpServers` do config

Otwórz plik:
```bash
open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Lub w terminalu:
```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Przed zmianą** plik wygląda tak:
```json
{
  "coworkUserFilesPath": "/Users/doomdoja/Claude",
  "preferences": { ... }
}
```

**Po zmianie** dodaj `mcpServers` na poziomie głównym (obok `preferences`):
```json
{
  "coworkUserFilesPath": "/Users/doomdoja/Claude",
  "preferences": { ... },
  "mcpServers": {
    "doomdoja-agent": {
      "command": "/opt/homebrew/bin/python3",
      "args": [
        "/Users/doomdoja/qwen-agent/mcp/server.py",
        "--mode",
        "stdio"
      ],
      "env": {
        "PYTHONPATH": "/Users/doomdoja/qwen-agent",
        "OLLAMA_URL": "http://localhost:11434",
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Gotowy snippet jest w: `~/qwen-agent/manager/claude_desktop_mcp_snippet.json`

### Krok 2 — Zrestartuj Claude Desktop

```
Cmd+Q → ponownie otwórz aplikację Claude
```

Lub przez menu: **Claude → Quit Claude**, potem uruchom ponownie.

### Krok 3 — Weryfikacja

W nowej rozmowie w Claude Desktop wpisz:
```
Jakie narzędzia masz dostępne?
```

Powinieneś zobaczyć narzędzia: `web_search`, `agent_task`, `scraper_fetch` itd.

---

## Szybki skrypt do wklejenia snippetu

Jeśli chcesz zautomatyzować merge (wymaga `python3 -m pip install jq` lub pythona):

```bash
python3 - <<'PYEOF'
import json, pathlib

cfg_path = pathlib.Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
snippet_path = pathlib.Path.home() / "qwen-agent/manager/claude_desktop_mcp_snippet.json"

cfg = json.loads(cfg_path.read_text())
snippet = json.loads(snippet_path.read_text())

# Dodaj/nadpisz klucz mcpServers
cfg["mcpServers"] = snippet["mcpServers"]

# Backup
backup = cfg_path.with_suffix(".json.bak")
backup.write_text(cfg_path.read_text())
print(f"Backup: {backup}")

cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
print("OK — zrestartuj Claude Desktop")
PYEOF
```

> Skrypt robi backup do `.json.bak` przed modyfikacją — bezpieczne do uruchomienia.

---

## Troubleshooting

**Serwer nie startuje:**
```bash
python3 ~/qwen-agent/mcp/server.py --list
# powinno wypisać listę narzędzi
```

**Ollama nie działa:**
```bash
curl http://localhost:11434/api/tags
# jeśli błąd: ollama serve &
```

**Logi serwera MCP** (gdy działa przez Claude Desktop) są w:
```
~/Library/Logs/Claude/mcp-server-doomdoja-agent.log
```
