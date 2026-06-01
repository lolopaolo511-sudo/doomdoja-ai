# Integracja: Vision/OCR Pipeline

## Przepływ
launchd + Make.com (folder watch → agent → Airtable dashboard)

## Przepływ szczegółowy
1. launchd plist monitoruje folder `~/incoming-docs/`
2. Nowy plik → wywołanie `vision_cli.py` z path jako argumentem
3. Agent wybiera model (qwen-vision dla obrazów, nomic dla tekstów)
4. JSON output → walidacja confidence → zapis do Airtable
5. Make.com HTTP webhook → generacja raportu PDF → zapis do tabeli Reports

## Make.com — jak podłączyć
1. Nowe scenario → **Webhooks → Custom webhook** → skopiuj URL
2. Wklej jako `MAKE_WEBHOOK_URL` w `.env`
3. Moduły po webhoku: **Airtable → Create Record** + opcjonalnie **Email → Send**

## Wymagane klucze (plik `.env` w ~/qwen-agent/)
```bash
AIRTABLE_API_KEY=<twój_token>
AIRTABLE_BASE_ID=<twoje_base_id>
MAKE_API_TOKEN=<twój_make_token>
MAKE_WEBHOOK_URL=<url_webhooka_ze_scenario>
OLLAMA_URL=http://localhost:11434
```
Rzeczywiste wartości — patrz `~/qwen-agent/.env` (plik lokalny, poza git).

## Tabele Airtable
- **Invoices**: Vendor, Date, Total, Currency, Items (JSON), Confidence, ImagePath, ProcessedAt
- **CVs**: Name, Experience (JSON), Skills (JSON), Education (JSON), Confidence, FilePath, ProcessedAt
- **Reports**: Type, AirtableRecordID, PDFPath, CreatedAt

## Model vision
- Wymagany model Ollama: `llava` lub `qwen2.5vl` (sprawdź `ollama list`)
- Fallback: `bakllava` dla starszych systemów

## launchd plist (przykład)
```xml
<!-- ~/Library/LaunchAgents/com.qwen.vision-watch.plist -->
<key>WatchPaths</key>
<array><string>/Users/doomdoja/incoming-docs</string></array>
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/python3</string>
  <string>/Users/doomdoja/qwen-agent/tools/vision_cli.py</string>
</array>
```
