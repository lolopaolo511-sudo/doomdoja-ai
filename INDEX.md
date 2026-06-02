# doomdoja-ai — Indeks systemu AI
> Ostatnia aktualizacja: 2026-06-02

---

## Infrastruktura globalna

| Komponent | Szczegóły |
|-----------|-----------|
| **Ollama** | `http://localhost:11434` — lokalny LLM runtime |
| **Model główny** | `deepseek-coder-v2:16b` (coding) |
| **Model vision** | `llava:7b` |
| **Model embed** | `nomic-embed-text` (RAG) |
| **Open WebUI** | `http://localhost:3000` — uruchom: `~/openwebui-setup/start.sh` |
| **Tailscale** | VPN do zdalnego dostępu |
| **Qdrant** | `http://localhost:6333` — vector DB (Docker) |
| **Make.com** | Workflow automation w chmurze — zastąpił n8n (etap B) |
| **SearxNG** | `http://localhost:8888` — lokalny search engine dla agentów |
| **Airtable** | CRM / baza leadów (konfiguracja w `.env`) |
| **Docker stack** | `~/doomdoja-stack/` — Colima + docker-compose (Qdrant, SearxNG, Caddy) |

---

## Komponenty / Projekty

### 🤖 qwen-agent — Orchestrator multi-agentowy
- **Ścieżka:** `~/qwen-agent/`
- **GitHub:** [lolopaolo511-sudo/doomdoja-ai](https://github.com/lolopaolo511-sudo/doomdoja-ai) — main, zsynchronizowany
- **Uruchomienie:**
  ```bash
  python3 ~/qwen-agent/multiagent/orchestrator.py "zadanie" --profile <profil>
  python3 ~/qwen-agent/multiagent/orchestrator.py "..." --plan-only   # dry-run
  ```
- **Profile:** `~/qwen-agent/prompt-library/` — `01-lead-generation`, itd.
- **Zależności:** Ollama, Airtable API, n8n webhook

### 🕷️ qwen-scraper — Pipeline scrapingowy
- **Ścieżka:** `~/qwen-scraper/`
- **GitHub:** [lolopaolo511-sudo/qwen-scraper](https://github.com/lolopaolo511-sudo/qwen-scraper) — main, zsynchronizowany
- **Rozmiar:** 378 MB (głównie `.venv` — gitignored)
- **Uruchomienie:** `python3 demo_stage1.py` / `demo_stage2.py` / `demo_stage3.py`
- **Stage 1:** Playwright scraping | **Stage 2:** Ollama extraction | **Stage 3:** ReAct agent | **Stage 4:** launchd scheduler
- **Zależności:** Playwright, Ollama, pandas, launchd (macOS)

### 📚 qwen-rag — RAG nad dokumentami i kodem
- **Ścieżka:** `~/qwen-rag/`
- **GitHub:** [lolopaolo511-sudo/qwen-rag](https://github.com/lolopaolo511-sudo/qwen-rag) — main, zsynchronizowany
- **Uruchomienie:**
  ```bash
  python3 ~/qwen-rag/ingest.py <plik>    # indeksowanie
  python3 ~/qwen-rag/query.py "pytanie"  # zapytanie
  ```
- **Vector DB:** ChromaDB (lokalnie, `chroma_db/` — gitignored) lub Qdrant (port 6333)
- **Zależności:** ChromaDB / Qdrant, `nomic-embed-text` via Ollama

### 👁️ qwen-vision — Vision / multimodal
- **Ścieżka:** `~/qwen-vision/`
- **GitHub:** [lolopaolo511-sudo/qwen-vision](https://github.com/lolopaolo511-sudo/qwen-vision) — main, zsynchronizowany
- **Uruchomienie:** `python3 ~/qwen-vision/vision_cli.py <obraz>`
- **Model:** `llava:7b` via Ollama
- **Zależności:** Ollama + llava:7b

### 🧪 qwen-lab — Benchmarki modeli
- **Ścieżka:** `~/qwen-lab/`
- **GitHub:** [lolopaolo511-sudo/qwen-lab](https://github.com/lolopaolo511-sudo/qwen-lab) — main, zsynchronizowany
- **Uruchomienie:** `./run_benchmark.sh <model>` lub `./benchmark_tasks.sh`
- **Wyniki:** `results/` (gitignored, generowane)

### 🛒 scraper-product — Produktyzowany scraper (Upwork gig)
- **Ścieżka:** `~/scraper-product/`
- **GitHub:** [lolopaolo511-sudo/scraper-product](https://github.com/lolopaolo511-sudo/scraper-product) — main, zsynchronizowany
- **Uruchomienie:** `python3 pipeline/main.py --config config.yaml`
- **Wyjścia:** Excel + PDF raporty, Airtable, Slack/email, n8n workflow
- **Konfiguracja:** `config.yaml` + `.env` (secrets — nigdy do gita)

### 🌐 openwebui-setup — Open WebUI (UI dla Ollamy)
- **Ścieżka:** `~/openwebui-setup/`
- **Git:** NIE (venv 2.3 GB — bez sensu trackować)
- **Uruchomienie:** `~/openwebui-setup/start.sh`
- **Port:** `http://localhost:3000`
- **Dane:** `~/openwebui-setup/data/`

### 🎮 MarioClone — Klon Mario (Python/pygame)
- **Ścieżka:** `~/MarioClone/`
- **GitHub:** [lolopaolo511-sudo/MarioClone](https://github.com/lolopaolo511-sudo/MarioClone) — main, zsynchronizowany
- **Uruchomienie:** `python3 main.py`

### 🎮 GodotMario — Klon Mario (Godot)
- **Ścieżka:** `~/GodotMario/`
- **GitHub:** [lolopaolo511-sudo/GodotMario](https://github.com/lolopaolo511-sudo/GodotMario) — main, zsynchronizowany
- **Uruchomienie:** Godot Engine → otwórz `project.godot`

### 🎮 IcyTower — Icy Tower (HTML/JS)
- **Ścieżka:** `~/IcyTower/`
- **GitHub:** [lolopaolo511-sudo/IcyTower](https://github.com/lolopaolo511-sudo/IcyTower) — main, zsynchronizowany
- **Uruchomienie:** otwórz `index.html` w przeglądarce

---

## Produkcyjne rozszerzenia (2026-06-01)

### 🔌 MCP Layer — klient i serwer MCP (v2 BLOK 1)
- **Ścieżka:** `~/qwen-agent/mcp/`
- **Uruchomienie serwera:**
  ```bash
  python3 ~/qwen-agent/mcp/server.py --mode stdio    # stdio (Claude Desktop)
  python3 ~/qwen-agent/mcp/server.py --mode http     # HTTP :8765
  ```
- **Klient:** `python3 ~/qwen-agent/mcp/client.py --server local_qwen --list`
- **Narzędzia:** `web_search`, `vision_ocr`, `agent_task`, `gig_finder`, `rag_query`, `scraper_fetch`
- **Konfiguracja:** `~/qwen-agent/mcp/servers.yaml`
- **Smoke test:** `python3 ~/qwen-agent/mcp/smoke_test.py` → 13/13 PASS

### 🔀 Hybrid Router — automatyczny wybór modelu (v2 BLOK 4)
- **Ścieżka:** `~/qwen-agent/router/`
- **Pliki:**
  - `router.py` — `choose_model(task, ctx)` → `RouterDecision`
  - `config.yaml` — progi złożoności, listy słów kluczowych, modele
  - `backends/local.py` — wrapper na istniejący `LLMClient` (Ollama)
  - `backends/cloud.py` — Anthropic Claude API (SDK lub httpx fallback)
  - `demo.py` — 3 przykłady decyzji bez realnego LLM
- **Aktywacja cloud:** `export ANTHROPIC_API_KEY=sk-ant-...` (lub `.env`)
  - Brak klucza → tryb LOCAL-ONLY (bezpieczny default, nie crashuje)
- **Wymuszenie local:** `python3 orchestrator.py "..." --force-local`
- **Demo:**
  ```bash
  python3 ~/qwen-agent/router/demo.py
  ```
- **Testy:** `python3 -m pytest tests/test_router.py` → 23/23 PASS (mock cloud)
- **Sygnały decyzyjne:**
  1. Złożoność (długość, słowa kluczowe architektura/database/deployment, kroki plannera)
  2. Prywatność (hasł/password/secret/token/PESEL → zawsze local, bez wyjątku)
  3. Eskalacja verifier (N porażek → cloud jeśli dostępny)
- **Raport:** na końcu sesji orchestratora `[ROUTER] Raport decyzji sesji` (które kroki gdzie)

### ✅ Verifier + Planner v2 (v2 BLOK 3)
- **Ścieżka:** `~/qwen-agent/multiagent/verifier.py` + `planner.py` (v2)
- **Uruchomienie verifier CLI:**
  ```bash
  python3 ~/qwen-agent/multiagent/verifier.py ~/projekt/index.html
  ```
- **Orchestrator z --verify (domyślnie ON):**
  ```bash
  python3 ~/qwen-agent/multiagent/orchestrator.py "zadanie" --verify --max-verify-rounds 3
  python3 ~/qwen-agent/multiagent/orchestrator.py "zadanie" --resume --work-dir ~/projekt
  ```
- **Typy weryfikacji:** Python (ast+pytest), HTML/gra (canvas,loop), JS (node), JSON
- **Dowód IcyTower3:** `python3 ~/qwen-agent/evals/icytower3_proof.py`
  - BROKEN: verifier wykrywa 4 braki uczciwie (nie udaje sukcesu)
  - FULL: gra Icy Tower 4.4KB przechodzi ✓ — plik: `~/IcyTower3/index.html`

---

## Tabela statusów v2 (2026-06-02)

| Blok | Moduł | Status | Smoke test |
|------|-------|--------|------------|
| BLOK 1 | MCP klient (`mcp/client.py`) | ✅ | 13/13 PASS |
| BLOK 1 | MCP serwer (`mcp/server.py`) | ✅ | raw JSON-RPC OK |
| BLOK 3 | Planner v2 (`multiagent/planner.py`) | ✅ | acceptance_criteria + state |
| BLOK 3 | Verifier (`multiagent/verifier.py`) | ✅ | Python/HTML/JS/JSON |
| BLOK 3 | Orchestrator --verify | ✅ | pętla poprawek 3 rundy |
| BLOK 3 | Dowód IcyTower3 | ✅ | BROKEN=FAIL, FULL=PASS |
| BLOK 4 | Hybrid Router (`router/router.py`) | ✅ | 23/23 unit tests PASS |
| BLOK 4 | Cloud backend (`router/backends/cloud.py`) | ✅ | local-only gdy brak klucza |
| BLOK 4 | Router demo (`router/demo.py`) | ✅ | 5/5 scenariuszy OK |
| BLOK 4 | Orchestrator --force-local | ✅ | wpięty w orchestrator |

---

## Ocena: o ile realnie urosła zdolność agenta

### Co faktycznie się poprawiło (BLOK 1–4):
1. **MCP klient** — agent może wywoływać narzędzia z zewnętrznych serwerów MCP bez dodatkowego kodu.
2. **MCP serwer** — nasze narzędzia dostępne dla Claude Desktop i innych aplikacji MCP-compatible.
3. **Verifier** — agent przestaje "udawać sukces". Weryfikuje canvas, pętlę gry, składnię, pytest.
4. **Planner v2 + state** — zadania wznawialne po przerwaniu, acceptance criteria dla codera.
5. **Hybrid Router (BLOK 4)** — automatyczny wybór modelu per zadanie/krok:
   - Proste → `qwen2.5-coder:7b` (szybki, lokalny, bez kosztu)
   - Złożone → `claude-opus-4-8` cloud (jeśli klucz dostępny)
   - Dane wrażliwe → zawsze local, bez wyjątku
   - Eskalacja po N porażkach verifier → cloud automatycznie

### Szczera ocena routera — o ile podniesie skuteczność "za pierwszym razem":

**Wzrost realny: umiarkowany (+15–25 pp przy złożonych zadaniach), nie rewolucyjny.**

Dlaczego:
- Router poprawnie identyfikuje złożone zadania i eskaluje je do mocniejszego modelu.
  Dla zadań architektonicznych (pełna aplikacja, system + deployment + baza danych)
  Claude Opus jest **znacząco** lepszy niż deepseek-coder:16b w jednym przejściu.
- Ale skuteczność "za pierwszym razem" zależy też od jakości promptów plannera,
  granularności kroków, i od tego czy verifier ma do czego się przyczepić.
  Router sam w sobie nie naprawi złego promptu ani zbyt dużego kroku.

**Co naprawdę podniesie skuteczność:**
- Cloud dostępny → zadania 5–8 kroków z integracjami powinny kończyć się sukcesem
  w 1–2 rundach zamiast 3 (bo Opus nie "gubi kontekstu" w długim planie).
- Eskalacja verifier → zamiast zapętlonej pętli poprawek z lokalnym modelem który
  nie rozumie swojego błędu, po 2 próbach wchodzi cloud i naprawia problem.
- Prywatność → zero ryzyka wycieku danych wrażliwych do API.

**Gdzie router NIE pomoże:**
- Zadania złożone ale źle sformułowane → cloud też nie domknie
- Brak ANTHROPIC_API_KEY → tryb local-only, identycznie jak bez routera
- Zadania wymagające realnego wykonania kodu (testy e2e, Playwright) → to problem
  codera/verifier, nie routera

### Co nadal jest słabością:
- Router robi decyzję na podstawie słów kluczowych i długości, nie semantyki.
  Krótkie zadanie z `system` lub `debug` dostanie wyższy score niż na to zasługuje.
- Brak feedback loop: router nie wie czy cloud rzeczywiście pomógł w tej konkretnej sesji.
  (Dobre rozszerzenie: po sukcesie/porażce zapisać do AgentMemory jaki backend zadziałał.)
- Cloud backend kosztuje — przy intensywnym użyciu z otwartym kluczem koszty rosną szybko.

---

### 🔒 Caddy — Reverse Proxy HTTPS + Auth (ETAP 1)
- **Ścieżka:** `~/doomdoja-stack/caddy/Caddyfile`
- **TLS:** internal CA (self-signed) lub Tailscale cert
- **Routing:** `/portal/ /docs/ /dashboard/ /chat/` z basic auth (bcrypt)
- **Uruchomienie:** `docker compose up -d caddy` (w ~/doomdoja-stack)
- **Dostęp:** `https://doomdojas-mac-mini.taild47341.ts.net/<ścieżka>`

### 🚀 Onboarding klienta — new_client.py (ETAP 3)
- **Ścieżka:** `~/scraper-product/onboarding/new_client.py`
- **Użycie:** `python3 onboarding/new_client.py --name "Klient X" [--dry-run]`
- **Tworzy:** folder klienta, config.yaml, README, make_scenario.md, launchd entry
- **Klienci:** `~/scraper-product/clients/<slug>/`

### 💳 Stripe billing — portal (ETAP 4)
- **Ścieżka:** `~/scraper-product/portal/stripe_billing.py`
- **Routes:** `/billing`, `/billing/checkout`, `/billing/webhook`, `/billing/status`
- **Tryb MOCK:** domyślny gdy brak kluczy (STRIPE_MOCK=true w .env)
- **Live:** STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET + STRIPE_PRICE_ID w .env

### 💾 Backup & Restore (ETAP 6)
- **Ścieżka:** `~/doomdoja-stack/backup/backup.sh` + `restore.sh`
- **Zakres:** Caddy, n8n, Qdrant snapshots, prompt-library, scraper-product
- **Launchd:** `com.doomdoja-stack.backup` — codziennie 02:00 → `~/backups/`
- **Rotacja:** 7 dni. Sekrety: `--encrypt-env` (openssl aes-256-cbc)

### 🔄 CI z bramką eval (ETAP 7)
- **Ścieżka:** `.github/workflows/ci.yml`
- **Joby:** unit-tests (pytest 17 testów) + eval-gate (eval_lite.py, próg 70%)
- **Eval-lite:** mock Ollama, deterministic — działa na GitHub-hosted runner
- **Eval-real:** zakomentowany — wymaga self-hosted runnera z Ollama (instrukc. w pliku)

---

## Status GitHub (2026-06-01)

| Projekt | GitHub | Synced |
|---------|--------|--------|
| qwen-agent | ✅ [doomdoja-ai](https://github.com/lolopaolo511-sudo/doomdoja-ai) | ✅ |
| qwen-scraper | ✅ [qwen-scraper](https://github.com/lolopaolo511-sudo/qwen-scraper) | ✅ |
| qwen-rag | ✅ [qwen-rag](https://github.com/lolopaolo511-sudo/qwen-rag) | ✅ |
| qwen-vision | ✅ [qwen-vision](https://github.com/lolopaolo511-sudo/qwen-vision) | ✅ |
| qwen-lab | ✅ [qwen-lab](https://github.com/lolopaolo511-sudo/qwen-lab) | ✅ |
| scraper-product | ✅ [scraper-product](https://github.com/lolopaolo511-sudo/scraper-product) | ✅ |
| openwebui-setup | — (2.3 GB venv, bez sensu) | — |
| MarioClone | ✅ [MarioClone](https://github.com/lolopaolo511-sudo/MarioClone) | ✅ |
| GodotMario | ✅ [GodotMario](https://github.com/lolopaolo511-sudo/GodotMario) | ✅ |
| IcyTower | ✅ [IcyTower](https://github.com/lolopaolo511-sudo/IcyTower) | ✅ |

**WSZYSTKO JEST NA GITHUBIE** (poza openwebui-setup, który jest za duży).

---

## Szybkie komendy

```bash
# Start Ollamy
ollama serve

# Start Open WebUI
~/openwebui-setup/start.sh

# Start Docker stack (Qdrant, n8n, SearxNG)
cd ~/doomdoja-stack && docker compose up -d

# Dry-run orchestratora
python3 ~/qwen-agent/multiagent/orchestrator.py "zadanie" --profile 01-lead-generation --plan-only

# RAG — zaindeksuj i zapytaj
python3 ~/qwen-rag/ingest.py plik.py && python3 ~/qwen-rag/query.py "jak działa X"

# Benchmark modeli
cd ~/qwen-lab && ./run_benchmark.sh deepseek-coder-v2:16b
```

---

## Archiwum

- `~/_archive/smoke-tests/` — stare smoke testy z `~/projects/qwen-smoke` i `~/projekty/test-agent`
