# Manager — warstwa kolejkowania zadań

Lekka warstwa między użytkownikiem a lokalnym agentem Ollama.  
Łatwe zadania trafiają do `deepseek-coder-v2:16b` (za darmo), trudne są eskalowane do clouda.

## Struktura katalogów

```
manager/
├── inbox/          ← wrzuć tutaj plik zadania (JSON/YAML)
├── processing/     ← daemon przenosi tu podczas przetwarzania
├── outbox/         ← gotowe wyniki (<id>.json)
├── failed/         ← błędy (<id>.json + <id>.error.json)
├── logs/           ← logi daemona (jeden plik na dzień)
│
├── daemon.py               ← daemon kolejki (start/stop/status)
├── local_do.py             ← CLI "local-do"
├── triage.py               ← classify_task() — local vs escalate
├── launchd_install.sh      ← instalacja autostartu przez launchd
├── com.doomdoja.agent-manager.plist  ← plik launchd
│
├── TRIAGE.md               ← tabela decyzji: co lokalnie, co eskalować
├── MCP_SETUP.md            ← instrukcja podpięcia do Claude Desktop
└── claude_desktop_mcp_snippet.json   ← gotowy snippet do claude_desktop_config.json
```

## Szybki start

### 1. Uruchom daemon

```bash
# Jednorazowo (foreground):
python3 ~/qwen-agent/manager/daemon.py --start

# Z autostarter przez launchd (zalecane):
~/qwen-agent/manager/launchd_install.sh install
```

### 2. Wyślij zadanie przez CLI

```bash
# Podstawowe użycie:
local-do "napisz funkcję Python licz_vat z testem pytest"

# Wymuś lokalny model:
local-do "parsuj CSV po nagłówkach" --local

# Router decyduje (local lub cloud jeśli klucz ustawiony):
local-do "zaprojektuj architekturę systemu" --auto

# Z limitem tokenów:
local-do "napisz CRUD SQLite" --budget 1024

# Async — nie czekaj na wynik:
local-do "długie zadanie" --async
local-do --result ldо_20260604_120000_abc123  # pobierz później

# Status kolejki:
local-do --status
local-do --list
```

### 3. Wrzuć zadanie ręcznie (JSON)

```json
// ~/qwen-agent/manager/inbox/moje_zadanie.json
{
  "id": "moje_zadanie_001",
  "task": "napisz parser CSV dla pliku z nagłówkami id,nazwa,cena",
  "mode": "local",
  "max_tokens": 1024,
  "priority": 7
}
```

## Format pliku zadania

| Pole | Typ | Opis |
|------|-----|------|
| `id` | string | Unikalny identyfikator (bez spacji) |
| `task` | string | Treść zadania w języku naturalnym |
| `mode` | `local` / `auto` | `local` = wymuś Ollama; `auto` = router decyduje |
| `max_tokens` | int | Limit tokenów (opcjonalne) |
| `priority` | int 1–10 | Wyższy = przetwarzany wcześniej (opcjonalne, def. 5) |

## Format wyniku w outbox/

| Pole | Opis |
|------|------|
| `status` | `done` lub `failed` |
| `output` | Odpowiedź modelu |
| `model_used` | Nazwa modelu który odpowiedział |
| `backend` | `local` lub `cloud` |
| `tokens_estimated` | Szacowana liczba tokenów w odpowiedzi |
| `duration_s` | Czas przetwarzania w sekundach |
| `verifier_passed` | Czy odpowiedź nie jest pusta / poprawna |
| `error` | Komunikat błędu lub `null` |
| `completed_at` | ISO timestamp zakończenia |

## Tabela statusów zadania

| Status | Katalog | Opis |
|--------|---------|------|
| ⏳ Oczekuje | `inbox/` | Plik wrzucony, daemon jeszcze nie odebrał |
| ⚙️ Przetwarza | `processing/` | Daemon wyciągnął i wysłał do modelu |
| ✅ Gotowe | `outbox/` | Wynik zapisany w `<id>.json` |
| ❌ Błąd | `failed/` | Zadanie + plik `.error.json` z przyczyną |

## Komendy daemona

```bash
python3 manager/daemon.py --start    # uruchom (foreground)
python3 manager/daemon.py --stop     # zatrzymaj przez SIGTERM
python3 daemon.py --status           # status + liczniki kolejki

# Przez launchd:
launchd_install.sh install           # autostart + uruchom teraz
launchd_install.sh stop              # zatrzymaj
launchd_install.sh status            # status launchd + kolejka
launchd_install.sh uninstall         # usuń autostart
```

## Triax — kiedy local, kiedy cloud

Szczegółowa tabela: [`TRIAGE.md`](TRIAGE.md)

```python
from manager.triage import classify_task, explain

print(explain("napisz parser CSV"))        # 🏠 LOCAL
print(explain("zaprojektuj architekturę")) # ☁️  ESCALATE (jeśli score >= 6)
```

## MCP — podpięcie do Claude Desktop

Gotowy snippet i instrukcja: [`MCP_SETUP.md`](MCP_SETUP.md)

Serwer MCP (`~/qwen-agent/mcp/server.py`) wystawia 6 narzędzi:
`web_search`, `vision_ocr`, `agent_task`, `gig_finder`, `rag_query`, `scraper_fetch`
