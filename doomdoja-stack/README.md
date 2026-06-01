# doomdoja-stack

Lokalny AI-stack: Qdrant · n8n · SearxNG — działający przez Colima (Docker bez GUI).

## Wymagania

- macOS (Apple Silicon) z zainstalowanym `colima` i `docker` (przez `brew`)
- Colima uruchomiony: `colima start --cpu 4 --memory 7 --disk 60`

## Uruchomienie od zera

```bash
cd ~/doomdoja-stack
cp .env.example .env          # opcjonalnie dostosuj
docker compose up -d
```

## Porty i adresy

| Usługa  | Lokalnie                      | Tailscale (100.123.85.25)          |
|---------|-------------------------------|-------------------------------------|
| Qdrant  | http://localhost:6333          | http://100.123.85.25:6333           |
| n8n     | http://localhost:5678          | http://100.123.85.25:5678           |
| SearxNG | http://localhost:8888          | http://100.123.85.25:8888           |
| Ollama  | http://localhost:11434 (native)| http://100.123.85.25:11434          |
| Dashboard | http://localhost:8080 (native)| http://100.123.85.25:8080          |

Wszystkie porty słuchają wyłącznie na `127.0.0.1` — dostęp z zewnątrz tylko przez Tailscale.

## Pierwsze uruchomienie n8n

Wejdź na http://localhost:5678 i załóż konto właściciela (jednorazowy ekran setup).
Następnie: Workflows → Import → wybierz plik z `n8n-workflows/`.

Dostępne workflow:
- `n8n-workflows/webhook-agent-demo.json` — Webhook → tworzenie zadania agenta → zapis wyniku
- `~/scraper-product/n8n/workflow.json` — Schedule → scraper pipeline → Airtable + Slack

## Zarządzanie usługami

```bash
# Status wszystkich kontenerów
docker compose ps

# Zatrzymaj (dane są zachowane w ./data/)
docker compose stop

# Zatrzymaj i usuń kontenery (dane zostają)
docker compose down

# Uruchom ponownie
docker compose up -d

# Logi konkretnej usługi
docker compose logs -f n8n
docker compose logs -f qdrant
docker compose logs -f searxng

# Restart pojedynczej usługi
docker compose restart searxng
```

## Autostart po reboocie

Autostart jest skonfigurowany przez launchd (`~/Library/LaunchAgents/com.doomdoja.stack.plist`).
Uruchamia `colima start` + `docker compose up -d` przy każdym logowaniu.

```bash
# Sprawdź status
launchctl list | grep doomdoja

# Wyłącz autostart
launchctl unload ~/Library/LaunchAgents/com.doomdoja.stack.plist

# Włącz ponownie
launchctl load ~/Library/LaunchAgents/com.doomdoja.stack.plist
```

## RAG (Qdrant)

```bash
# Zaindeksuj katalog
/usr/bin/python3 ~/qwen-rag/ingest_qdrant.py ~/qwen-scraper

# Zapytaj (Qdrant backend)
/usr/bin/python3 ~/qwen-rag/query_qdrant.py "jak działa scraper?"

# Przez oryginalny query.py z --backend
/usr/bin/python3 ~/qwen-rag/query.py "jak działa scraper?" --backend qdrant

# Migracja z ChromaDB → Qdrant
/usr/bin/python3 ~/qwen-rag/migrate_chroma_to_qdrant.py
```

## Web search w agencie (SearxNG)

```bash
# Standalone test narzędzia
/usr/bin/python3 ~/qwen-agent/tools/web_search.py "Python asyncio"

# Przez ReAct agenta (qwen-scraper)
cd ~/qwen-scraper && .venv/bin/python3 -c "
from agent.runner import AgentRunner
runner = AgentRunner(model='qwen2.5-coder:7b', max_steps=5)
print(runner.run('Wyszukaj najnowsze informacje o Qdrant vector store'))
"
```
