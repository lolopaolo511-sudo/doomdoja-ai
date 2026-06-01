# Prompt Library — qwen-agent Multi-Agent System

Biblioteka profili projektowych dla systemu multi-agent (Planner + Coder + Reviewer + ReAct)
działającego na Ollama (deepseek-coder-v2 / qwen2.5) z integracjami n8n + Airtable + GitHub.

## Struktura

```
prompt-library/
├── 01-lead-generation/      # B2B Lead Generation & Follow-up
├── 02-vision-ocr/           # Vision/OCR Pipeline (faktury, CV, zdjęcia)
└── 03-rag-knowledge-base/   # RAG Knowledge Base dla firmy
```

Każdy profil zawiera:

| Plik            | Opis                                                      |
|-----------------|-----------------------------------------------------------|
| `system.md`     | System prompt — rola i zasady agenta                      |
| `planner.md`    | Prompt dla roli Planner — podział na kroki                |
| `coder.md`      | Prompt dla roli Coder — implementacja                     |
| `reviewer.md`   | Prompt dla roli Reviewer — ocena i poprawki               |
| `example-task.md` | Przykładowe zadanie do testów                           |
| `integration.md` | Integracje (n8n, Airtable, launchd) i wymagane klucze   |
| `profile.yaml`  | Metadane: modele, narzędzia, ścieżki, tabele Airtable     |

## Użycie z orchestratorem

```bash
# Uruchom z profilem (dry-run — nie wymaga kluczy)
python3 multiagent/orchestrator.py "zadanie" --profile 01-lead-generation --plan-only

# Pełne uruchomienie (wymaga Ollamy + kluczy Airtable/n8n)
python3 multiagent/orchestrator.py "Znajdź 20 firm AI" --profile 01-lead-generation

# Vision OCR
python3 multiagent/orchestrator.py "Przetwórz fakturę faktura.png" --profile 02-vision-ocr

# RAG Knowledge Base
python3 multiagent/orchestrator.py "Jaka jest polityka urlopowa?" --profile 03-rag-knowledge-base
```

## Profile

### 01 — Lead Generation & Intelligent Follow-up
**Cel:** Scrape leadów → score → personalizowany follow-up (email/LinkedIn) → log w Airtable + reminder w n8n.

**Modele:** deepseek-coder-v2:16b  
**Narzędzia:** Playwright, Airtable API, n8n webhook  
**Airtable:** tabele Leads + FollowUps

### 02 — Vision/OCR Pipeline
**Cel:** Zdjęcie/faktura/CV → strukturyzowany JSON → zapis do Airtable + raport.

**Modele:** deepseek-coder-v2:16b + llava (vision)  
**Narzędzia:** vision_cli.py, Airtable API, n8n webhook  
**Airtable:** tabele Invoices + CVs + Reports

### 03 — RAG Knowledge Base
**Cel:** Wewnętrzna baza wiedzy firmy → pytania z cytatami.

**Modele:** deepseek-coder-v2:16b + nomic-embed-text  
**Narzędzia:** qwen-rag/query.py, Chroma/Qdrant, Airtable  
**Airtable:** tabele Documents + QueryLog

## Wymagania

- Ollama uruchomiony lokalnie (`ollama serve`)
- Model `deepseek-coder-v2:16b` pobrany (`ollama pull deepseek-coder-v2:16b`)
- Klucze API (tylko do realnych uruchomień, nie dry-run):
  - `AIRTABLE_API_KEY` + `AIRTABLE_BASE_ID`
  - `N8N_WEBHOOK_URL`
  - Opcjonalnie: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
