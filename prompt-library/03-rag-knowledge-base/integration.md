# Integracja: RAG Knowledge Base

## Przepływ
n8n (nowy dokument → embed + Airtable log) + dashboard na 8080

## Przepływ szczegółowy
1. Nowy dokument trafia do `~/company-docs/`
2. n8n trigger (folder watch lub webhook) → wywołanie `add_documents(folder_path)`
3. nomic-embed-text tworzy embeddingi → Chroma/Qdrant zapis
4. Log nowego dokumentu do Airtable (tabela: Documents)
5. Dashboard (port 8080) → interfejs do zapytań z cytatami
6. Log każdego zapytania do Airtable (tabela: QueryLog)

## Wymagane klucze (environment variables)
- `AIRTABLE_API_KEY` — Personal Access Token
- `AIRTABLE_BASE_ID` — ID bazy
- `N8N_WEBHOOK_URL` — URL webhooka n8n
- `OLLAMA_URL` — URL Ollama (domyślnie http://localhost:11434)
- `CHROMA_PATH` — ścieżka do bazy Chroma (domyślnie ~/qwen-rag/chroma/)

## Tabele Airtable
- **Documents**: Filename, Path, ChunkCount, EmbeddedAt, Status
- **QueryLog**: Question, Answer, Sources (JSON), Timestamp, UsefulFeedback

## Wymagane modele Ollama
- `nomic-embed-text` — embeddingi (sprawdź `ollama list`)
- `deepseek-coder-v2:16b` — odpowiedzi / synthesis

## Uruchomienie dashboardu
```bash
cd ~/qwen-rag && python3 dashboard.py --port 8080
```
