# Integracja: RAG Knowledge Base

## Przepływ
Make.com (nowy dokument → embed + Airtable log) + dashboard na 8080

## Przepływ szczegółowy
1. Nowy dokument trafia do `~/company-docs/`
2. Make.com trigger (Watch Files lub Webhook) → wywołanie `add_documents(folder_path)`
3. nomic-embed-text tworzy embeddingi → Chroma/Qdrant zapis
4. Log nowego dokumentu do Airtable (tabela: Documents)
5. Dashboard (port 8080) → interfejs do zapytań z cytatami
6. Log każdego zapytania do Airtable (tabela: QueryLog)

## Make.com — jak podłączyć
1. Nowe scenario → **Webhooks → Custom webhook** → skopiuj URL
2. Wklej jako `MAKE_WEBHOOK_URL` w `.env`
3. Moduły: **HTTP → Make a Request** do lokalnego agenta + **Airtable → Create Record**

## Wymagane klucze (plik `.env` w ~/qwen-agent/)
```bash
AIRTABLE_API_KEY=<twój_token>
AIRTABLE_BASE_ID=<twoje_base_id>
MAKE_API_TOKEN=<twój_make_token>
MAKE_WEBHOOK_URL=<url_webhooka_ze_scenario>
OLLAMA_URL=http://localhost:11434
CHROMA_PATH=~/qwen-rag/chroma/
```
Rzeczywiste wartości — patrz `~/qwen-agent/.env` (plik lokalny, poza git).

## Tabele Airtable
- **Documents**: Filename, Path, ChunkCount, EmbeddedAt, Status
- **QueryLog**: Question, Answer, Sources (JSON), Timestamp, UsefulFeedback

## Wymagane modele Ollama
- `nomic-embed-text` — embeddingi (`ollama pull nomic-embed-text`)
- `deepseek-coder-v2:16b` — odpowiedzi / synthesis

## Uruchomienie dashboardu
```bash
cd ~/qwen-rag && python3 dashboard.py --port 8080
```
