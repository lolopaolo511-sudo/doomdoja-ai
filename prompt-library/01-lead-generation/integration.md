# Integracja: Lead Generation

## n8n workflow
RSS/Scrape → agent webhook → Airtable + Telegram powiadomienie

## Przepływ danych
1. n8n trigger (RSS feed / manual) → POST do agent webhook
2. Agent scrape (Playwright) → score → draft wiadomości
3. Zapis do Airtable (tabela: Leads, FollowUps)
4. Webhook do n8n → Telegram powiadomienie o nowym leadzie
5. n8n reminder workflow → follow-up po X dniach

## Wymagane klucze (environment variables)
- `AIRTABLE_API_KEY` — Personal Access Token z airtable.com
- `AIRTABLE_BASE_ID` — ID bazy (np. appXXXXXXXX)
- `N8N_WEBHOOK_URL` — URL webhooka n8n (np. http://localhost:5678/webhook/leads)
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — opcjonalne

## Tabele Airtable
- **Leads**: Name, Company, Source, FitScore, IntentScore, Status, CreatedAt
- **FollowUps**: LeadID (link), Message, Channel (Email/LinkedIn), ScheduledAt, SentAt
