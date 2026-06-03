# doomdoja-ai — Indeks systemu AI
> Ostatnia aktualizacja: 2026-06-03

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

## Rozbudowa zdolności agenta (2026-06-03)

### 🖥️ BLOK 1 — Computer/Browser Use (`computer_use/`)
- **Ścieżka:** `~/qwen-agent/computer_use/`
- **Narzędzia ReAct:** `navigate(url)`, `read_page(selector?)`, `click(selector, confirm?)`,
  `type_text(selector, text)`, `extract(schema)`, `screenshot(name?)`
- **Bezpieczniki:** whitelist domen (`config.yaml`), submit/buy/delete wymagają `confirm=True`,
  każda akcja logowana do `~/.qwen_agent/computer_use_logs/`
- **Desktop read-only:** `desktop_screenshot()` przez `screencapture` — tylko podgląd
- **Rejestracja:** `register_computer_use_tools(my_registry)` — 7 narzędzi
- **Demo:**
  ```bash
  python3 ~/qwen-agent/computer_use/demo.py
  # quotes.toscrape: nawigacja+odczyt ✓ | httpbin form: fill bez submit ✓
  ```

### 🧠 BLOK 2 — Pamięć 2.0 (`memory2/`)
- **Ścieżka:** `~/qwen-agent/memory2/`
- **3 typy pamięci:**
  - `semantic` — fakty i wiedza; wektory na Qdrant (`agent_semantic`) + SQLite fallback
  - `episodic` — zdarzenia i przebiegi zadań z timestamp, outcome, task_id
  - `procedural` — wyuczone procedury: kroki, success_rate, statystyki runów
- **Unified API:** `Memory2.remember(type, content, tags, meta)` / `recall(query, type?)` / `forget(type, id)`
- **Auto-kontekst:** `recall_context(task)` → gotowy blok do wklejenia w prompt agenta
- **CLI:** `python3 memory2/cli.py remember semantic "fakt"` / `recall "pytanie"`
- **Demo:**
  ```bash
  python3 ~/qwen-agent/memory2/demo.py
  # Zapis 3 typy + recall + recall_context — PASS
  ```

### 🔄 BLOK 3 — Self-Improvement Closed-Loop (`self_improve/` + `evals/`)
- **Nowe pliki:**
  - `self_improve/closed_loop.py` — pętla: błąd → analiza LLM → patch → eval przed/po → kandydat
  - `evals/swe_tasks.yaml` — 6 SWE-bench zadań (bug_fix×3, impl×2, refactor×1) z exec testami
  - `evals/swe_runner.py` — runner: LLM generuje kod → subprocess exec → pass/fail; `--code-override`
- **Przepływ:** error → `analyze_error()` → `PatchProposal` → eval przed → eval po → `EvalComparison` →
  jeśli delta ≥ 0 → kandydat zapisany do `proposals/` jako `candidate_*.md` — **NIE auto-merge**
- **Demo:**
  ```bash
  python3 -c "
  from self_improve.closed_loop import ClosedLoop
  loop = ClosedLoop()
  loop.run_demo()   # wstrzyknięty off-by-one → wykryto → patch → eval +100pp
  "
  ```
- **SWE runner:**
  ```bash
  python3 evals/swe_runner.py --task swe_fix_offbyone --code-override "def fizzbuzz(n): ..."
  ```

### 📊 BLOK 4 — Feedback Loop Routera (`router/`)
- **Nowe pliki:**
  - `router/feedback.py` — `RouterFeedback`: loguje decyzje do memory2 episodic; `record_outcome()`
  - `router/calibration.py` — `calibrate(stats)` → kalibracja progów:
    local_rate ≥ 80% → `force_local`; cloud uplift < 5% → `no_escalate`; local < 40% → obniż verifier_escalate
  - `router/report.py` — raport ASCII tabela per (backend, task_class) + kalibracja
- **Zintegrowano z `router.py`:** `_log_and_record()` → `fb.log_decision()`;
  `record_verifier_result()` → `fb.record_outcome()`; kalibracja załadowana przy init
- **Demo (mock 82 decyzji):**
  ```bash
  python3 ~/qwen-agent/router/report.py --mock
  # Wynik: simple/private → force_local, complex → eskalacja (+54pp cloud uplift)
  ```

---

## Tabela statusów v3 (2026-06-03)

| Blok | Moduł | Status | Weryfikacja |
|------|-------|--------|-------------|
| v3 BLOK 1 | `computer_use/browser_agent.py` (navigate/read/click/type/extract/screenshot) | ✅ | Playwright demo PASS |
| v3 BLOK 1 | `computer_use/desktop.py` (desktop_screenshot) | ✅ | screencapture (sandbox: degraded OK) |
| v3 BLOK 1 | `computer_use/register.py` (7 narzędzi) | ✅ | register_computer_use_tools PASS |
| v3 BLOK 2 | `memory2/semantic.py` (Qdrant + SQLite fallback) | ✅ | Qdrant REST + recall PASS |
| v3 BLOK 2 | `memory2/episodic.py` (zdarzenia SQLite) | ✅ | recall "router cloud" PASS |
| v3 BLOK 2 | `memory2/procedural.py` (procedury + success_rate) | ✅ | recall "scraping" PASS |
| v3 BLOK 2 | `memory2/memory2.py` (unified API + recall_context) | ✅ | recall_context blok PASS |
| v3 BLOK 3 | `evals/swe_tasks.yaml` (6 SWE zadań) | ✅ | buggy=FAIL, fixed=PASS |
| v3 BLOK 3 | `evals/swe_runner.py` (exec testy) | ✅ | subprocess exec PASS |
| v3 BLOK 3 | `self_improve/closed_loop.py` | ✅ | delta=+100pp → kandydat zapisany |
| v3 BLOK 4 | `router/feedback.py` (log + record_outcome) | ✅ | memory2 integration PASS |
| v3 BLOK 4 | `router/calibration.py` (reguły kalibracji) | ✅ | force_local/no_escalate PASS |
| v3 BLOK 4 | `router/report.py` (raport + mock demo) | ✅ | ASCII tabela PASS |
| v3 BLOK 4 | `router/router.py` (feedback integration) | ✅ | log_decision + record_outcome wpiąte |

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

### 🖨️ print-lab — Pipeline wydruku 3D (Elegoo Centauri Carbon)
- **Ścieżka:** `~/print-lab/`
- **Git:** lokalny (bez remote — push odłożony)
- **Uruchomienie:**
  ```bash
  # Pełny pipeline: parametry → STL → G-code → plan PDF
  python3 ~/print-lab/scripts/pipeline.py phone_stand --params phone_w=75 --material PLA
  python3 ~/print-lab/scripts/pipeline.py --demo   # demo gotowe

  # Tylko model
  python3 ~/print-lab/scripts/generate_model.py --list
  python3 ~/print-lab/scripts/generate_model.py box_organizer --params outer_w=120

  # Tylko plan z istniejącego G-code
  python3 ~/print-lab/scripts/slice_and_plan.py model.stl --material PETG
  ```
- **Szablony OpenSCAD:** `phone_stand`, `cable_clip`, `box_organizer` (parametryczne, specs YAML)
- **Profile:** PLA, PETG, CF-Nylon × PrusaSlicer CLI + OrcaSlicer/ElegooSlicer JSON
- **Drukarka:** Elegoo Centauri Carbon, 256×256×256mm, CoreXY, dysza 0.4mm hartowana
- **Zależności:** OpenSCAD (brew), PrusaSlicer (brew), pyyaml, reportlab
- **Demo wynik:** stojak na telefon PLA → 1h 13m, 18g, 0.45 PLN

---

### 📄 cv-creator — Generator CV z lokalnym LLM + Hybrid Router (2026-06-03)
- **Ścieżka:** `~/cv-creator/`
- **Git:** lokalny (bez remote, commit `b8ba630`)
- **Uruchomienie:**
  ```bash
  # CLI — demo
  cd ~/cv-creator && python3 cli/main.py --demo

  # CLI — własne dane
  python3 cli/main.py --cv dane.yaml --job ogłoszenie.txt --cover-letter --lang pl

  # Web UI (FastAPI)
  cd ~/cv-creator && python3 -m uvicorn api.app:app --reload
  # → http://localhost:8000

  # Testy
  python3 -m pytest tests/ -v   # → 26/26 PASS
  ```
- **Wejście:** YAML/JSON z danymi kandydata + opcjonalny opis ogłoszenia
- **Wyjście:** PDF + DOCX w 3 szablonach (modern / classic / ats-plain)
- **Szablony:** modern (kolor, czytelny), classic (tradycyjny), ats-plain (ATS-safe, no tables)
- **Routing per sekcja:**
  - Summary, bullets, skills → 🏠 LOCAL (deepseek-coder-v2:16b / qwen:7b)
  - Cover letter (score 6-7) → ☁️ CLOUD Claude Opus gdy `ANTHROPIC_API_KEY` ustawiony
- **Jakość local-only:** 6/10 — CV gotowe do edycji; cover letter szablonowy
- **Jakość z cloud:** 8.5/10 — cover letter przekonujący, tailoring wyraźnie lepszy
- **Dwujęzyczność:** `--lang pl|en` — całe CV i prompty w wybranym języku
- **Zależności:** fastapi, uvicorn, reportlab, python-docx, anthropic, pyyaml, httpx (już zainstalowane)
- **Integracja z routerem:** `~/qwen-agent/router/router.py` — `HybridRouter` importowany bezpośrednio

---

## Ocena: o ile realnie urosła zdolność agenta

### Szczera ocena v3 (2026-06-03) — BLOK 1–4:

**Wzrost realny: umiarkowany, ale konkretny. Nie jest to skok jakościowy — to wypełnianie infrastruktury.**

#### BLOK 1 — Browser Use: +++ realna wartość
- Agent może teraz autonomicznie scrapeować strony, wypełniać formularze i wyodrębniać dane strukturalne.
- `extract(schema)` przez LLM to rzeczywisty przyrost — wcześniej trzeba było pisać XPath/CSS ręcznie.
- `desktop_screenshot()` jest dekoracją — read-only bez klikania ma ograniczoną wartość praktyczną.
- Ograniczenie: whitelist domen jest bezpieczna ale wymaga ręcznej edycji `config.yaml` przy każdej nowej stronie.

#### BLOK 2 — Pamięć 2.0: +++ infrastruktura gotowa, użyteczność zależy od integracji
- 3 typy pamięci to właściwa architektura — episodic/semantic/procedural mają różne zastosowania.
- `recall_context()` to kluczowa funkcja: agent może teraz "pamiętać" jak robił coś podobnego.
- Słabość: semantyczny recall w języku polskim przez nomic-embed jest słabszy niż angielski.
  Ranking nie zawsze zwraca tę samą treść co query — to feature modelu, nie bug kodu.
- Pamięć nie jest jeszcze wpiąta w orchestrator (zostało jako `TODO`).

#### BLOK 3 — Self-Improvement: + infrastruktura, brak realnego loop bez LLM
- SWE runner z exec testami to solidna podstawa do mierzenia postępu — lepszy niż substring-matching.
- `closed_loop.py` jest poprawnie zarchitekturowany: zawsze wymaga human review, nie auto-merge.
- Ograniczenie: "closed" loop jest naprawdę zamknięty tylko jeśli LLM jest online. Bez Ollamy
  analiza jest pusta, patch to placeholder. Demo bez LLM musi używać hard-coded fixed_code.
- Wartość: mamy teraz metrykę do porównywania "przed i po" — to ważniejsze niż sam patcher.

#### BLOK 4 — Router Feedback: ++ spójne domknięcie, wartość zależy od danych
- Kalibracja na podstawie historii to sensowny algorytm — `force_local` gdy local_rate ≥ 80%.
- Problem: potrzeba N ≥ 3 decyzji per (backend, task_class) żeby kalibracja cokolwiek zrobiła.
  Na nowej instalacji przez pierwsze 20-30 sesji kalibracja jest "brak zmian".
- Raport `--mock` pokazuje jak system będzie wyglądał z dojrzałymi danymi — to ważne.

#### Co naprawdę podniesie skuteczność (priorytet do zrobienia):
1. **Wpiąć memory2 w orchestrator** — `recall_context(task)` jako pierwszy krok każdego zadania
2. **Rozszerzyć whitelist browser** + przetestować na rzeczywistych zadaniach scrapingu
3. **Zebrać 30+ decyzji routera** żeby kalibracja miała na czym działać
4. **SWE runner z modelem** — uruchomić `swe_runner.py` z deepseek-coder i zmierzyć baseline

### Co faktycznie się poprawiło (BLOK 1–4 v2):
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

## Status GitHub (2026-06-03)

| Projekt | Widoczność | URL repo | Push |
|---------|-----------|----------|------|
| qwen-agent | 🔒 prywatne | https://github.com/lolopaolo511-sudo/doomdoja-ai | ⏳ wymaga gh auth |
| qwen-scraper | 🔒 prywatne | https://github.com/lolopaolo511-sudo/qwen-scraper | ⏳ wymaga gh auth |
| qwen-rag | 🔒 prywatne | https://github.com/lolopaolo511-sudo/qwen-rag | ⏳ wymaga gh auth |
| qwen-vision | 🔒 prywatne | https://github.com/lolopaolo511-sudo/qwen-vision | ⏳ wymaga gh auth |
| qwen-lab | 🔒 prywatne | https://github.com/lolopaolo511-sudo/qwen-lab | ⏳ wymaga gh auth |
| scraper-product | 🔒 prywatne | https://github.com/lolopaolo511-sudo/scraper-product | ⏳ wymaga gh auth |
| daily-market-pl | 🔒 prywatne | https://github.com/lolopaolo511-sudo/daily-market-pl | ⏳ nowe repo + push |
| pricing-calculator | 🔒 prywatne | https://github.com/lolopaolo511-sudo/pricing-calculator | ⏳ nowe repo + push |
| gmail-automation | 🔒 prywatne | https://github.com/lolopaolo511-sudo/gmail-automation | ⏳ nowe repo + push |
| cv-creator | 🔒 prywatne | https://github.com/lolopaolo511-sudo/cv-creator | ⏳ nowe repo + push |
| print-lab | 🔒 prywatne | https://github.com/lolopaolo511-sudo/print-lab | ⏳ nowe repo + push |
| doomdoja-stack | 🔒 prywatne | https://github.com/lolopaolo511-sudo/doomdoja-stack | ⏳ nowe repo + push |
| MarioClone | 🌍 publiczne | https://github.com/lolopaolo511-sudo/MarioClone | ⏳ wymaga gh auth |
| GodotMario | 🌍 publiczne | https://github.com/lolopaolo511-sudo/GodotMario | ⏳ wymaga gh auth |
| IcyTower | 🌍 publiczne | https://github.com/lolopaolo511-sudo/IcyTower | ⏳ wymaga gh auth |
| IcyTower2 | 🌍 publiczne | https://github.com/lolopaolo511-sudo/IcyTower2 | ⏳ nowe repo + push |
| IcyTower3 | 🌍 publiczne | https://github.com/lolopaolo511-sudo/IcyTower3 | ⏳ nowe repo + push |
| openwebui-setup | — | — (2.3 GB venv, nie trackować) | — |

**Lokalnie wszystko gotowe. Wymagany `gh auth login` + 1 komenda push-all (patrz sekcja Push).**

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
