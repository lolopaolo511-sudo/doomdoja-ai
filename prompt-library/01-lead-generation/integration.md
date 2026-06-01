# Integracja: Lead Generation

## Make.com scenario
Scrape/RSS → agent webhook → Airtable + Telegram powiadomienie

## Przepływ danych
1. Make.com trigger (Webhook lub RSS/HTTP module) → POST do agent webhook
2. Agent scrape (Playwright) → score → draft wiadomości
3. Zapis do Airtable (tabela: Leads, FollowUps)
4. Make.com HTTP module → Telegram powiadomienie o nowym leadzie
5. Make.com scheduler scenario → follow-up reminder po X dniach

## Make.com — jak podłączyć webhook
1. Zaloguj się na make.com
2. Nowe scenario → dodaj moduł **Webhooks → Custom webhook**
3. Skopiuj URL webhooka (postać: `https://hook.eu2.make.com/XXXXXXXX`)
4. Wklej jako `MAKE_WEBHOOK_URL` w `.env`
5. Dodaj kolejne moduły: **Airtable → Create Record**, **Telegram → Send Message**

## Wymagane klucze (plik `.env` w ~/qwen-agent/)
```bash
AIRTABLE_API_KEY=<twój_token>
AIRTABLE_BASE_ID=<twoje_base_id>
MAKE_API_TOKEN=<twój_make_token>
MAKE_WEBHOOK_URL=<url_webhooka_ze_scenario>
TELEGRAM_BOT_TOKEN=<opcjonalne>
TELEGRAM_CHAT_ID=<opcjonalne>
```
Rzeczywiste wartości — patrz `~/qwen-agent/.env` (plik lokalny, poza git).

## Tabele Airtable
- **Leads**: Name, Company, Source, FitScore, IntentScore, Status, CreatedAt
- **FollowUps**: LeadID (link), Message, Channel (Email/LinkedIn), ScheduledAt, SentAt

## Make.com API (opcjonalne — automatyczne tworzenie scenarios)
```python
import httpx, os
MAKE_API = "https://www.make.com/api/v2"
headers = {"Authorization": f"Token {os.getenv('MAKE_API_TOKEN')}"}
# Lista scenarios
resp = httpx.get(f"{MAKE_API}/scenarios", headers=headers)
```
