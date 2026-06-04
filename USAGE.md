# doomdoja-ai — Kompletna instrukcja użytkowania

> Autor: doomdoja | Model: deepseek-coder-v2:16b + qwen2.5-coder | Data: 2026-06-03

---

## Spis treści

1. [Tabela portów i adresów](#tabela-portów)
2. [Lokalny agent / multi-agent](#lokalny-agent--multi-agent)
3. [Hybrid Router — local vs cloud](#hybrid-router--local-vs-cloud)
   - [Router Feedback + Raport](#router-feedback--raport)
4. [Computer/Browser Use](#computerbrowser-use-v3)
5. [Pamięć 2.0 (memory2)](#pamięć-20-memory2-v3)
6. [Self-Improvement / Eval](#self-improvement--eval-v3)
4. [aider — autonomiczny koder](#aider--autonomiczny-koder)
5. [Continue.dev — IDE autocomplete](#continuedev--ide-autocomplete)
6. [Scraper (qwen-scraper)](#scraper-qwen-scraper)
7. [Pipeline scraper-product](#pipeline-scraper-product)
8. [RAG (qwen-rag)](#rag-qwen-rag)
9. [Vision / OCR (qwen-vision)](#vision--ocr-qwen-vision)
10. [Gig Finder](#gig-finder)
11. [Dashboard (:8080)](#dashboard-8080)
12. [Open WebUI — czat (:3000)](#open-webui--czat-3000)
13. [Stack Docker (doomdoja-stack)](#stack-docker-doomdoja-stack)
14. [Portal klientów](#portal-klientów)
15. [Jak rozmawiać z lokalnym agentem](#jak-rozmawiać-z-lokalnym-agentem)
16. [Codzienny workflow](#codzienny-workflow)

---

## Tabela portów

| Usługa | URL lokalny | URL Tailscale | Opis |
|--------|------------|---------------|------|
| Dashboard | http://localhost:8080 | http://doomdoja-m4:8080 | Panel zarządzania agentami |
| Open WebUI | http://localhost:3000 | http://doomdoja-m4:3000 | Czat z lokalnymi modelami |
| Qdrant | http://localhost:6333 | — | Baza wektorowa (RAG) |
| SearxNG | http://localhost:8888 | — | Metawyszukiwarka (gig-finder) |
| n8n | http://localhost:5678 | — | Automatyzacje workflow |
| Caddy/proxy | http://localhost:80 | — | Reverse proxy |
| Portal klientów | http://localhost:8090 | — | Onboarding + billing Stripe |
| Ollama API | http://localhost:11434 | — | LLM backend |

---

## Lokalny agent / multi-agent

**Co robi:** Orkiestrator Planner → Coder → Reviewer wykonuje złożone zadania programistyczne przez lokalny model (deepseek-coder-v2:16b). Każda rola to osobne wywołanie LLM.

**Jak uruchomić:**
```bash
# Jednorazowy setup (fix importu)
ln -sf ~/qwen-agent /tmp/qwen_agent

# Uruchomienie
cd ~/qwen-agent/multiagent
PYTHONPATH=/tmp python3 orchestrator.py "ZADANIE" --work-dir ~/moj-projekt --max-rounds 2
```

**Przykład użycia:**
```bash
PYTHONPATH=/tmp python3 orchestrator.py \
  "Napisz skrypt Python który pobiera ceny kryptowalut z CoinGecko API i zapisuje do CSV" \
  --work-dir ~/projekty/crypto-tracker \
  --max-rounds 3
```

**Tryb dry-run (tylko plan, bez LLM):**
```bash
PYTHONPATH=/tmp python3 orchestrator.py "zadanie" --plan-only --work-dir /tmp/test
```

**Dostępne modele (OLLAMA):**
- `deepseek-coder-v2:16b` — domyślny, najlepszy do kodu
- `qwen2.5-coder:14b` — alternatywa, dobry do dużych plików
- `qwen2.5-coder:7b` — szybszy, słabszy
- `llava:7b` — vision tasks (nie do kodu)

**Typowe problemy:**
- `ModuleNotFoundError: No module named 'qwen_agent'` → `ln -sf ~/qwen-agent /tmp/qwen_agent`
- Timeout → zmniejsz zadanie lub użyj `--max-rounds 1`
- Niekompletny plik → dla HTML/Frontend lokalny 16B model generuje fragmenty, nie pełne pliki

---

## Hybrid Router — local vs cloud

**Co robi:** automatycznie wybiera backend LLM (lokalny Ollama lub cloud Claude) per krok zadania, zależnie od złożoności, prywatności i historii verifier.

### Aktywacja cloud fallback

```bash
# Dodaj do .env (NIE commituj klucza!)
echo "ANTHROPIC_API_KEY=sk-ant-..." >> ~/qwen-agent/.env

# Lub jednorazowo w sesji
export ANTHROPIC_API_KEY=sk-ant-...
```

Bez klucza → **tryb LOCAL-ONLY** (bezpieczny default, router działa normalnie, nie crashuje, loguje ostrzeżenie).

### Wymuszenie lokalnego modelu

```bash
# Dla całego zadania (np. dane klienta, prywatny kod)
cd ~/qwen-agent/multiagent
python3 orchestrator.py "zadanie" --force-local

# Router automatycznie wymusza local gdy wykryje słowa wrażliwe:
# hasło/password/secret/token/PESEL/credential/bearer → zawsze local
```

### Demo decyzji routera (bez realnego LLM)

```bash
python3 ~/qwen-agent/router/demo.py
```

Wyświetla 5 scenariuszy: prosty→local, złożony→cloud, eskalacja, brak klucza, dane wrażliwe.

### Jak czytać raport routingu

Na końcu każdego zadania orchestrator drukuje:

```
[ROUTER ] ╔═══════════════════════════════════════════════════════╗
[ROUTER ] ║          ROUTER — Raport decyzji sesji                ║
[ROUTER ] ╚═══════════════════════════════════════════════════════╝
[ROUTER ]   Krok 1 (planner):
[ROUTER ]     Backend : 🏠 LOCAL
[ROUTER ]     Model   : qwen2.5-coder:7b
[ROUTER ]     Powód   : lokalny: score=1 < próg=6
[ROUTER ]   Krok 2 (verifier-fix runda 1):
[ROUTER ]     Backend : ☁️  CLOUD
[ROUTER ]     Model   : claude-opus-4-8
[ROUTER ]     Powód   : eskalacja: verifier zawiódł 2x (próg: 2)
[ROUTER ]   Podsumowanie: LOCAL=1  CLOUD=1  eskalacje=1  privacy-protected=0
```

### Dostrojenie progów

Edytuj `~/qwen-agent/router/config.yaml`:

```yaml
thresholds:
  complexity_score_cloud: 6   # score >= 6 → cloud (obniż aby częściej używać cloud)
  verifier_fails_escalate: 2  # po 2 porażkach verifier → cloud
  task_length_complex: 500    # znaki — powyżej tej długości +1 pkt złożoności

cloud:
  model: "claude-opus-4-8"   # model cloud (zmień np. na claude-sonnet-4-6)
```

### Testy routera (mock cloud, bez kluczy)

```bash
cd ~/qwen-agent
python3 -m pytest tests/test_router.py -v   # 23/23 PASS
```

---

## aider — autonomiczny koder

**Co robi:** aider to AI-powered asystent do kodowania w terminalu. Łączy się z lokalnym Ollama i edytuje pliki bezpośrednio w repozytorium git, z automatycznym commitem.

**Jak uruchomić:**
```bash
cd /moj-projekt-git
aider --model ollama_chat/deepseek-coder-v2:16b --edit-format whole --yes
```

**Lub przez agent_runner (zadania z kolejki):**
```bash
# Dodaj zadanie
echo "Dodaj obsługę błędów do funkcji parse_invoice()" > ~/qwen-agent/tasks/pending/001-error-handling.txt

# Uruchom runner
cd ~/qwen-agent
python3 agent_runner.py --repo ~/moj-projekt --max-retries 3
```

**Przykład użycia:**
```bash
cd ~/qwen-scraper
aider --model ollama_chat/deepseek-coder-v2:16b --yes --message \
  "Dodaj retry z exponential backoff do playwright_scraper.py"
```

**Typowe problemy:**
- aider wymaga repozytorium git w katalogu (`git init` jeśli brak)
- Duże pliki (>500 linii) — użyj `--edit-format diff` zamiast `whole`
- Aider nie działa bez Ollamy → `ollama serve` najpierw

---

## Continue.dev — IDE autocomplete

**Co robi:** Rozszerzenie do VS Code / JetBrains, które daje autocomplete i chat zasilany lokalnym modelem Ollama.

**Jak uruchomić:**
1. VS Code → Extensions → szukaj "Continue"
2. Już zainstalowany i skonfigurowany na `deepseek-coder-v2:16b`
3. Skrót: `Cmd+I` (inline edit), `Cmd+L` (czat w panelu)

**Przykład użycia:**
- Zaznacz funkcję → `Cmd+I` → wpisz "dodaj docstring i obsługę wyjątków"
- `Cmd+L` → "jak działa ta funkcja?" — wyjaśnienie w kontekście pliku

**Typowe problemy:**
- Brak autocomplete → sprawdź czy Ollama działa: `curl http://localhost:11434/api/tags`
- Wolno odpowiada → normalnie dla 16B modelu na M4, pierwsze odpowiedzi ładują model (~30s)

---

## Scraper (qwen-scraper)

**Co robi:** 4-etapowy scraping: Playwright pobiera strony → LLM wyciąga dane → ReAct agent nawiguje złożone serwisy → pipeline przetwarza i zapisuje.

**Struktura:**
```
~/qwen-scraper/
  scraper/playwright_scraper.py  — pobieranie stron
  scraper/llm_extractor.py       — ekstrakcja danych przez LLM
  pipeline/                       — ETL pipeline
  scheduler/                      — launchd scheduler
  agent/                          — ReAct agent do złożonej nawigacji
```

**Jak uruchomić:**
```bash
cd ~/qwen-scraper

# Scrape jednej strony
python3 demo_stage1.py --url "https://example.com" --output /tmp/dane.json

# Pełny pipeline (scrape → LLM extract → CSV)
python3 demo_stage2.py

# ReAct agent (nawigacja multi-step)
python3 demo_stage3.py --task "znajdź oferty pracy Python w Warszawie na LinkedIn"
```

**Przykład:**
```bash
cd ~/qwen-scraper
python3 scraper/playwright_scraper.py --url "https://news.ycombinator.com" \
  --save /tmp/hn.html
python3 scraper/llm_extractor.py --html /tmp/hn.html \
  --prompt "wyciągnij tytuły i linki do artykułów" --format json
```

**Typowe problemy:**
- `playwright install` jeśli brakuje przeglądarek
- Rate limiting → dodaj `--delay 2` (sekundy między requestami)
- Dynamiczne SPA → użyj `--wait-for-selector "div.content"`

---

## Pipeline scraper-product

**Co robi:** Gotowy produkt SaaS dla klientów: config.yaml definiuje źródła → pipeline scrape → Airtable sync → Excel+PDF raporty → Slack/email powiadomienia.

**Struktura:**
```
~/scraper-product/
  config.yaml             — konfiguracja klienta
  pipeline/               — główny pipeline
  reports/                — generowane raporty
  portal/main.py          — webowy portal klienta (:8090)
  n8n/                    — workflow automatyzacji
```

**Jak uruchomić:**
```bash
cd ~/scraper-product

# Uruchom pipeline dla domyślnego klienta
python3 pipeline/main.py --config config.yaml

# Portal klientów
python3 portal/main.py  # → http://localhost:8090
```

**Przykład:**
```bash
cd ~/scraper-product
# Edytuj config.yaml — dodaj nowego klienta
# Uruchom i sprawdź raport
python3 pipeline/main.py --config clients/jan_kowalski.yaml
ls reports/  # → jan_kowalski_2026-06-02.xlsx
```

**Typowe problemy:**
- Airtable API key → w `.env` lub `config.yaml`: `airtable_api_key`
- n8n webhook → sprawdź czy n8n działa: `curl http://localhost:5678/healthz`

---

## RAG (qwen-rag)

**Co robi:** Retrieval-Augmented Generation — indeksuje dokumenty w Qdrant (baza wektorowa) i odpowiada na pytania na podstawie ich treści.

**Jak uruchomić:**
```bash
cd ~/qwen-rag

# Zaindeksuj dokumenty
python3 ingest_qdrant.py --dir ~/dokumenty/ --collection moje-docs

# Zadaj pytanie
python3 query_qdrant.py --question "jakie są terminy płatności w umowie z XYZ?"
```

**Przykład:**
```bash
cd ~/qwen-rag
# Zaindeksuj PDF faktury
python3 ingest_qdrant.py --dir ~/faktury/ --collection faktury-2026
# Zapytaj
python3 query_qdrant.py \
  --question "ile zapłaciłem za hosting w maju 2026?" \
  --collection faktury-2026
```

**Typowe problemy:**
- Qdrant nie działa → `cd ~/doomdoja-stack && docker compose up -d qdrant`
- `nomic-embed-text` model embeddings → Ollama musi mieć ten model: `ollama pull nomic-embed-text`
- Brak wyników → sprawdź czy indeksowanie ukończono (logi w `/tmp/ingest.log`)

---

## Vision / OCR (qwen-vision)

**Co robi:** Analiza obrazów i OCR przez model `llava:7b` (Ollama). Wyciąga tekst z faktur, paragonów, zdjęć.

**Jak uruchomić:**
```bash
cd ~/qwen-vision

# Analiza obrazu
python3 vision_cli.py --image ~/zdjecie.jpg --prompt "co widać na zdjęciu?"

# OCR faktury
python3 vision_cli.py --image ~/faktura.png \
  --prompt "wyciągnij: numer faktury, datę, kwotę brutto, NIP sprzedawcy" \
  --format json
```

**Przykład:**
```bash
# Batch OCR paragony
for f in ~/paragony/*.jpg; do
  python3 ~/qwen-vision/vision_cli.py --image "$f" \
    --prompt "data, sklep, kwota total" --format json >> ~/paragony/wyniki.jsonl
done
```

**Typowe problemy:**
- `llava:7b` nie załadowany → `ollama pull llava:7b`
- Niska jakość OCR → upewnij się że obraz ma min. 150 DPI i dobre oświetlenie
- Dla długich dokumentów → podziel na strony przed wysłaniem

---

## Gig Finder

**Co robi:** Przeszukuje Upwork/inne platformy zleceniowe, ocenia ogłoszenia przez LLM pod kątem dopasowania do profilu (Piero Nocentini, AI/scraping expert), generuje raport HTML z rankingiem.

**Jak uruchomić:**
```bash
cd ~/qwen-agent/gig-finder
PYTHONPATH=/tmp python3 run_gig_finder.py

# Raport otwiera się automatycznie, lub:
open reports/gig_report_latest.html
```

**Konfiguracja profilu:**
```yaml
# ~/qwen-agent/gig-finder/config.yaml
profile:
  name: "Piero Nocentini"
  hourly_rate_min: 35
  hourly_rate_max: 120
  skills: [web scraping, python, LLM, airtable, n8n, ...]
```

**Przykład — harmonogram:**
```bash
# Uruchom codziennie o 8:00 (launchd już skonfigurowane)
ls ~/qwen-agent/gig-finder/launchd/
# Zainstaluj jeśli jeszcze nie:
cp ~/qwen-agent/gig-finder/launchd/*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.doomdoja.gigfinder.plist
```

**Typowe problemy:**
- SearxNG nie działa → `curl http://localhost:8888` → `cd ~/doomdoja-stack && docker compose up -d searxng`
- Brak raportów → sprawdź `~/qwen-agent/gig-finder/logs/`

---

## Dashboard (:8080)

**Co robi:** Webowy panel zarządzania agentami: lista zadań, logi, status Ollama, dodawanie zadań przez formularz, podgląd raportów gig-finder.

**Jak uruchomić:**
```bash
cd ~/qwen-agent
python3 dashboard/app.py
# → http://localhost:8080
```

**Autostart (launchd):**
Dashboard startuje automatycznie przy logowaniu przez:
`~/Library/LaunchAgents/com.doomdoja.dashboard.plist`

**Co pokazuje dashboard:**
- Status Ollama i dostępne modele
- Kolejka zadań (tasks/pending/)
- Logi ostatnich 10 uruchomień agenta
- Formularz "Dodaj zadanie" → trafia do kolejki
- Podgląd najnowszego raportu gig-finder
- Linki do wszystkich usług (Open WebUI, n8n, Qdrant)

**Typowe problemy:**
- Port zajęty → `lsof -i :8080` i `kill -9 PID`
- Brakujące pakiety → `pip3 install fastapi httpx jinja2`

---

## Open WebUI — czat (:3000)

**Co robi:** Graficzny czat (jak ChatGPT) zasilany lokalnymi modelami Ollama. Obsługuje historię rozmów, upload plików, system prompts.

**Jak otworzyć:** http://localhost:3000

**Dostępne modele w czacie:**
- `deepseek-coder-v2:16b` — programowanie
- `qwen2.5-coder:14b` — programowanie, dłuższy kontekst
- `llava:7b` — analiza obrazów (wgraj zdjęcie w czacie)
- `nomic-embed-text` — nie do czatu (embeddingi)

**Przykład — system prompt dla scrapera:**
W Open WebUI → "New Chat" → ikonka ustawień → System Prompt:
```
Jesteś ekspertem web scraping Python. Odpowiadaj po polsku. 
Zawsze podawaj gotowy kod z error handlingiem.
```

**Typowe problemy:**
- Open WebUI nie startuje → `docker ps | grep openwebui` lub sprawdź port 3000
- Model nie widoczny → `ollama list` i zrestartuj Open WebUI

---

## Stack Docker (doomdoja-stack)

**Co robi:** Zestaw usług: Qdrant (baza wektorowa), SearxNG (metawyszukiwarka), Caddy (proxy). Zarządzany przez Docker Compose.

**Jak uruchomić/zatrzymać:**
```bash
cd ~/doomdoja-stack
docker compose up -d        # start wszystkich
docker compose stop         # zatrzymanie
docker compose restart      # restart
docker compose ps           # status usług
docker compose logs -f      # logi live
```

**Usługi:**
| Kontener | Port | Opis |
|----------|------|------|
| caddy | 80, 443 | Reverse proxy / HTTPS |
| qdrant | 6333 | Baza wektorowa dla RAG |
| searxng | 8888 | Metawyszukiwarka (gig-finder) |

**Backup danych:**
```bash
cd ~/doomdoja-stack
./backup/backup.sh          # → ~/doomdoja-stack/backup/YYYY-MM-DD/
```

**Typowe problemy:**
- Docker nie działa → `colima start` (używamy Colima zamiast Docker Desktop)
- Port zajęty → `lsof -i :6333` i sprawdź czy inny Qdrant nie działa

---

## Portal klientów

**Co robi:** Webowa aplikacja FastAPI dla klientów: onboarding, przegląd raportów, płatności Stripe.

**Jak uruchomić:**
```bash
cd ~/scraper-product/portal
python3 main.py  # → http://localhost:8090
```

**Zarządzanie klientami:**
```bash
# Lista klientów
cat ~/scraper-product/clients/clients.json

# Onboarding nowego klienta
cp ~/scraper-product/config.yaml ~/scraper-product/clients/nowy_klient.yaml
# edytuj nowy_klient.yaml i uruchom pipeline
```

---

## MCP — klient i serwer (v2)

**Co robi:** Warstwa MCP (Model Context Protocol) pozwala agentowi łączyć się z zewnętrznymi
serwerami MCP (klient) i wystawiać własne narzędzia innym aplikacjom (serwer).

### Serwer MCP — uruchomienie

```bash
# Tryb stdio (do podłączenia jako MCP server w innych app)
python3 ~/qwen-agent/mcp/server.py --mode stdio

# Tryb HTTP (REST endpoint)
python3 ~/qwen-agent/mcp/server.py --mode http --port 8765

# Lista dostępnych narzędzi
python3 ~/qwen-agent/mcp/server.py --list
```

**Narzędzia serwera:** `web_search`, `vision_ocr`, `agent_task`, `gig_finder`, `rag_query`, `scraper_fetch`

### Klient MCP — użycie

```bash
# Listuj narzędzia serwera
python3 ~/qwen-agent/mcp/client.py --server local_qwen --list

# Wywołaj narzędzie
python3 ~/qwen-agent/mcp/client.py --server local_qwen \
  --call web_search --args '{"query": "python async"}'
```

**Użycie w kodzie (narzędzia MCP w pętli ReAct):**
```python
from mcp.client import load_mcp_tools
import sys; sys.path.insert(0, '/Users/doomdoja/qwen-agent')

mcp_tools = load_mcp_tools()        # załaduj z servers.yaml
all_tools = native_tools + mcp_tools  # wpnij do agenta
```

### Podłączenie do Claude Desktop

W `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "qwen-agent": {
      "command": "python3",
      "args": ["/Users/doomdoja/qwen-agent/mcp/server.py", "--mode", "stdio"]
    }
  }
}
```

### Konfiguracja serwerów

Edytuj `~/qwen-agent/mcp/servers.yaml` — włącz/wyłącz serwery (`enabled: true/false`).

### Smoke test

```bash
python3 ~/qwen-agent/mcp/smoke_test.py
```

---

## Verifier — twarda weryfikacja artefaktów (v2)

**Co robi:** Po każdej implementacji sprawdza artefakty pod kątem kompletności i poprawności.
Nie udaje sukcesu — uczciwie raportuje braki i przekazuje wskazówki naprawcze do codera.

```bash
# Weryfikuj pojedynczy plik
python3 ~/qwen-agent/multiagent/verifier.py ~/IcyTower3/index.html

# Weryfikuj katalog projektu
python3 ~/qwen-agent/multiagent/verifier.py ~/moj-projekt/
```

**Typy weryfikacji:**
| Typ | Co sprawdza |
|-----|-------------|
| Python | `ast.parse` + `py_compile` + `pytest` |
| HTML/game | DOCTYPE, html/head/body, `<canvas>`, `getContext()`, `requestAnimationFrame` |
| JS | `node --check` (lub heurystyki bez node) |
| JSON | `json.loads` |

### Orchestrator z --verify (domyślnie ON)

```bash
cd ~/qwen-agent
python3 multiagent/orchestrator.py "zadanie" --work-dir ~/projekt --verify
# lub wyraźnie:
python3 multiagent/orchestrator.py "zadanie" --no-verify     # v1 behavior
python3 multiagent/orchestrator.py "zadanie" --max-verify-rounds 3   # więcej rund poprawek

# Wznów przerwaną sesję
python3 multiagent/orchestrator.py "zadanie" --resume --work-dir ~/projekt
```

**Nowe flagi orchestratora:**
| Flaga | Domyślnie | Opis |
|-------|-----------|------|
| `--verify` | ON | Twarda weryfikacja po implementacji |
| `--no-verify` | — | Wyłącz verifier (v1 behavior) |
| `--max-verify-rounds N` | 3 | Max rund poprawek verifier |
| `--resume` | — | Wznów z plan_state.json |

### Dowód działania (IcyTower3)

```bash
# Scenariusz BROKEN → verifier wykrywa 4 braki (canvas, pętla gry, itp.)
# Scenariusz FULL   → gra przechodzi weryfikację ✓
python3 ~/qwen-agent/evals/icytower3_proof.py

# Z prawdziwym LLM (wymaga Ollamy)
python3 ~/qwen-agent/evals/icytower3_proof.py --with-llm
```

---

## Jak rozmawiać z lokalnym agentem

### W terminalu (orchestrator)

```bash
cd ~/qwen-agent/multiagent && PYTHONPATH=/tmp python3 orchestrator.py "ZADANIE"
```

**6 przykładów poleceń:**

**1. Budowa projektu Python:**
```bash
PYTHONPATH=/tmp python3 orchestrator.py \
  "Stwórz moduł Python do parsowania faktur PDF: wyciągaj numer, datę, kwotę, NIP. \
  Użyj pdfplumber. Zapisz jako ~/projekty/invoice-parser/parser.py z testami" \
  --work-dir ~/projekty/invoice-parser --max-rounds 3
```

**2. Scrape konkretnej strony:**
```bash
cd ~/qwen-scraper
python3 scraper/playwright_scraper.py --url "https://pracuj.pl/praca/python" \
  --save /tmp/oferty.html && \
python3 scraper/llm_extractor.py --html /tmp/oferty.html \
  --prompt "wyciągnij listę ofert: tytuł, firma, wynagrodzenie, lokalizacja" \
  --format json --output /tmp/oferty_python.json
```

**3. Pytanie RAG o dokumenty:**
```bash
cd ~/qwen-rag
python3 query_qdrant.py \
  --question "jakie były moje przychody z Upwork w Q1 2026?" \
  --collection faktury-2026
```

**4. OCR faktury/paragonu:**
```bash
python3 ~/qwen-vision/vision_cli.py \
  --image ~/Pobrane/faktura_hosting.png \
  --prompt "wyciągnij: sprzedawca, NIP, data, kwota netto, kwota brutto, VAT" \
  --format json
```

**5. Czat przez Open WebUI (GUI):**
```
Otwórz: http://localhost:3000
Wybierz model: deepseek-coder-v2:16b
Wpisz: "Napisz skrypt bash który codziennie o 7:00 robi backup ~/projekty/ do ~/backup/"
```

**6. Znalezienie zleceń Upwork:**
```bash
cd ~/qwen-agent/gig-finder
PYTHONPATH=/tmp python3 run_gig_finder.py && open reports/gig_report_latest.html
```

### W czacie (Open WebUI)

Otwórz http://localhost:3000 i pisz naturalnie:
- "jak naprawić ten błąd" + wklej traceback
- "zoptymalizuj tę funkcję SQL" + wklej kod
- Przeciągnij zdjęcie → "co widać na paragonie?"

---

## Codzienny workflow

```
08:00  ☕ Sprawdź dashboard: http://localhost:8080
         → czy Ollama działa? czy są nowe raporty gig-finder?
         → przejrzyj kolejkę zadań

08:15  📋 Gig Finder (jeśli nie uruchamia się automatycznie):
         cd ~/qwen-agent/gig-finder && PYTHONPATH=/tmp python3 run_gig_finder.py
         open reports/gig_report_latest.html

09:00  💻 Praca z aiderem / orchestratorem:
         Skrót: ~/Desktop/doomdoja-ai/🤖 Zapytaj agenta.command

12:00  📊 Pipeline dla klientów (jeśli scheduled nie zadziałał):
         cd ~/scraper-product && python3 pipeline/main.py

17:00  💾 Backup:
         ~/Desktop/doomdoja-ai/💾 Backup teraz.command

W dowolnym momencie:
  - Czat AI     → http://localhost:3000
  - OCR/vision  → python3 ~/qwen-vision/vision_cli.py --image PLIK
  - RAG query   → python3 ~/qwen-rag/query_qdrant.py --question "..."
```

---

---

## Computer/Browser Use (v3)

**Wymagania:** `pip install playwright && playwright install chromium`

```bash
# Demo: nawigacja + odczyt + wypełnienie formularza (bez submit)
python3 ~/qwen-agent/computer_use/demo.py

# Rejestracja narzędzi w własnym TOOL_REGISTRY
from computer_use.register import register_computer_use_tools
register_computer_use_tools(my_tool_list)  # dodaje 7 narzędzi

# Użycie bezpośrednie
from computer_use.browser_agent import BrowserAgent
import asyncio
async def main():
    agent = BrowserAgent(headless=True)
    await agent.navigate("http://quotes.toscrape.com")
    result = await agent.read_page(".quote .text")
    print(result.data["text"])
    await agent.close()
asyncio.run(main())

# Desktop screenshot (read-only, macOS)
from computer_use.desktop import desktop_screenshot
desktop_screenshot("podgląd.png")  # ~/.qwen_agent/screenshots/
```

**Dodaj domenę do whitelist:** edytuj `~/qwen-agent/computer_use/config.yaml` → `allowed_domains`.

---

## Pamięć 2.0 — memory2 (v3)

```bash
# CLI
python3 ~/qwen-agent/memory2/cli.py remember semantic "Python dict O(1)" --tags python
python3 ~/qwen-agent/memory2/cli.py remember episodic "Zadanie X ukończone" --outcome success --task-id t001
python3 ~/qwen-agent/memory2/cli.py remember procedural "Jak scrapować" --name scrape_table --steps "navigate" "read" "extract"
python3 ~/qwen-agent/memory2/cli.py recall "szybkość dict"
python3 ~/qwen-agent/memory2/cli.py recall "scraping" --type procedural
python3 ~/qwen-agent/memory2/cli.py recall "..." --context  # blok do wklejenia w prompt
python3 ~/qwen-agent/memory2/cli.py status

# Python API
from memory2 import Memory2
mem = Memory2()
mem.remember("semantic", "treść", tags=["tag"])
mem.remember("episodic", "zdarzenie", meta={"task_id":"x","outcome":"success"})
ctx = mem.recall_context("opis zadania")  # blok kontekstu do promptu
```

**Backend semantyczny:** Qdrant REST (`localhost:6333`, kolekcja `agent_semantic`).
Fallback SQLite gdy Qdrant niedostępny.

---

## Self-Improvement / Eval (v3)

```bash
# SWE runner — wszystkie zadania przez LLM
python3 ~/qwen-agent/evals/swe_runner.py --model deepseek-coder-v2:16b

# Konkretne zadanie z gotowym kodem (bez LLM)
python3 ~/qwen-agent/evals/swe_runner.py --task swe_fix_offbyone \
  --code-override "def fizzbuzz(n): return [str(i) for i in range(1,n+1)]"

# Closed-loop demo (wstrzyknięty bug → wykrycie → patch → eval)
cd ~/qwen-agent && python3 -c "
from self_improve.closed_loop import ClosedLoop
ClosedLoop().run_demo()
"

# Analiza nagromadzonych błędów
python3 ~/qwen-agent/self_improve/analyzer.py
# Propozycje: ~/qwen-agent/self_improve/proposals/ (DO REVIEW, nie auto-merge)
```

---

## Router Feedback + Raport

```bash
# Raport skuteczności (mock — bez danych historycznych)
python3 ~/qwen-agent/router/report.py --mock

# Raport z prawdziwych danych (po zebraniu historii decyzji)
python3 ~/qwen-agent/router/report.py

# JSON (do CI/dashboard)
python3 ~/qwen-agent/router/report.py --mock --json
```

Feedback jest zbierany automatycznie gdy router działa w orchestratorze.
Kalibracja ładuje się przy starcie routera jeśli w memory2 są dane (min. 3 próbki per klasa).

---

## Workflow Engine v1 (`workflow/`)

Warstwa orkiestracji — trzy prymitywy + 6 wzorców + budżet tokenów + quarantine.
Dokumentacja szczegółowa: `~/qwen-agent/workflow/README.md`

### Szybki start

```python
from workflow import agent, parallel, pipeline, WorkflowBudget, quarantine

# Subagent z izolowanym kontekstem i budżetem
budget = WorkflowBudget(total=5000)
r = agent("Oceń ogłoszenie", context=raw_text, token_budget=800, budget=budget)
print(r.output, r.backend, r.tokens_used)

# N agentów równolegle
tasks = [{"goal": f"Zadanie {i}", "context": dane[i]} for i in range(5)]
results = parallel(tasks, max_workers=4)

# Dane przez etapy
chain = pipeline(["Wyodrębnij fakty", "Oceń jakość", "Sformatuj JSON"],
                 initial_input="Treść dokumentu...")
```

### Wzorce

```bash
# Dostępne wzorce
from workflow.patterns import (
    classify_and_act,          # klasyfikacja → routing
    fan_out_and_synthesize,    # N równoległych → synteza
    adversarial_verification,  # wrogi weryfikator bez wiedzy o autorze
    generate_and_filter,       # generuj N → filtruj rubryką → top-K
    tournament,                # pairwise N² → ranking
    loop_until_done,           # iteruj z feedbackiem aż warunek
)
```

### Budżet tokenów (twardy limit)

```python
from workflow import WorkflowBudget, TokenBudgetExceeded

budget = WorkflowBudget(total=10000, label="mój-workflow")
# rzuca TokenBudgetExceeded PRZED wywołaniem LLM gdy przekroczony
print(budget.report())   # [mój-workflow] 0/10000 tokenów (0%)
```

### Quarantine — agenty z niezaufanymi danymi

```python
from workflow import quarantine, action_tool

@action_tool
def save_report(path, content): ...  # zablokowana w quarantine

with quarantine():
    r = agent("Analizuj dane z sieci", context=raw_html)
    # r.quarantined == True
    save_report(...)  # → QuarantineViolation!
```

### Runner — /goal i /loop

```python
from workflow import run_workflow, WorkflowConfig

cfg = WorkflowConfig(
    budget_tokens=8000,
    goal_condition="wynik zawiera ranking",
    loop=3,        # max 3 iteracje
)
result = run_workflow(my_workflow_fn, cfg=cfg)
print(result.report())
```

```bash
# CLI
python -m workflow.runner --goal "zawiera JSON" --loop 3 --budget 5000 --quarantine
python -m workflow.runner --dry-run
```

### Demo — Gig Finder na workflow

```bash
# Bez LLM (tylko fetch)
python3 ~/qwen-agent/workflow/demo_gig_finder.py --dry-run

# Pełne (wymaga Ollama działającego)
python3 ~/qwen-agent/workflow/demo_gig_finder.py --top 10 --budget 25000

# Jedno źródło
python3 ~/qwen-agent/workflow/demo_gig_finder.py --source remoteok --top 5
```

Stary gig-finder (`gig-finder/run_gig_finder.py`) działa bez zmian — demo workflow
to osobny plik demonstracyjny. Kluczowe różnice: scoring równoległy (3–6× szybciej)
+ adversarial filter (~20–40% odsiew fałszywych pozytywów).

---

*Dokumentacja wygenerowana: 2026-06-04 | System: doomdoja-ai | Mac M4*
