# Integracja: Vision/OCR Pipeline

## Przepływ
launchd + n8n (folder watch → agent → Airtable dashboard)

## Przepływ szczegółowy
1. launchd plist monitoruje folder `~/incoming-docs/`
2. Nowy plik → wywołanie `vision_cli.py` z path jako argumentem
3. Agent wybiera model (qwen-vision dla obrazów, nomic dla tekstów)
4. JSON output → walidacja confidence → zapis do Airtable
5. Webhook do n8n → generacja raportu PDF → zapis do tabeli Reports

## Wymagane klucze (environment variables)
- `AIRTABLE_API_KEY` — Personal Access Token
- `AIRTABLE_BASE_ID` — ID bazy
- `N8N_WEBHOOK_URL` — URL webhooka n8n
- `OLLAMA_URL` — URL Ollama (domyślnie http://localhost:11434)

## Tabele Airtable
- **Invoices**: Vendor, Date, Total, Currency, Items (JSON), Confidence, ImagePath, ProcessedAt
- **CVs**: Name, Experience (JSON), Skills (JSON), Education (JSON), Confidence, FilePath, ProcessedAt
- **Reports**: Type, AirtableRecordID, PDFPath, CreatedAt

## Model vision
- Wymagany model Ollama: `llava` lub `qwen2.5vl` (sprawdź `ollama list`)
- Fallback: `bakllava` dla starszych systemów
