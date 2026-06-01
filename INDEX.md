# doomdoja-ai — Indeks systemu AI
> Ostatnia aktualizacja: 2026-06-01

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
| **Airtable** | CRM / baza leadów (konfiguracja w `.env`) |
| **n8n** | Workflow automation / webhooki follow-up |

---

## Komponenty / Projekty

### 🤖 qwen-agent — Orchestrator multi-agentowy
- **Ścieżka:** `~/qwen-agent/`
- **GitHub:** `lolopaolo511-sudo/doomdoja-ai` (main branch, zsynchronizowany)
- **Uruchomienie:**
  ```bash
  python3 ~/qwen-agent/multiagent/orchestrator.py "zadanie" --profile <profil>
  python3 ~/qwen-agent/multiagent/orchestrator.py "..." --plan-only   # dry-run
  ```
- **Profile:** `~/qwen-agent/prompt-library/` — `01-lead-generation`, itd.
- **Zależności:** Ollama, Airtable API, n8n webhook

### 🕷️ qwen-scraper — Pipeline scrapingowy
- **Ścieżka:** `~/qwen-scraper/`
- **Git:** lokalnie tylko (brak remote), zainicjowany
- **Rozmiar:** 378 MB (głównie `.venv` — ignorowane)
- **Uruchomienie:** `python3 demo_stage1.py` / `demo_stage2.py` / `demo_stage3.py`
- **Stage 1:** Playwright scraping | **Stage 2:** Ollama extraction | **Stage 3:** ReAct agent | **Stage 4:** launchd scheduler
- **Zależności:** Playwright, Ollama, pandas, launchd (macOS)

### 📚 qwen-rag — RAG nad dokumentami i kodem
- **Ścieżka:** `~/qwen-rag/`
- **Git:** lokalnie tylko (brak remote)
- **Uruchomienie:**
  ```bash
  python3 ~/qwen-rag/ingest.py <plik>    # indeksowanie
  python3 ~/qwen-rag/query.py "pytanie"  # zapytanie
  ```
- **Vector DB:** ChromaDB (lokalnie, `chroma_db/` — gitignored)
- **Zależności:** ChromaDB, `nomic-embed-text` via Ollama

### 👁️ qwen-vision — Vision / multimodal
- **Ścieżka:** `~/qwen-vision/`
- **Git:** lokalnie tylko (brak remote)
- **Uruchomienie:** `python3 ~/qwen-vision/vision_cli.py <obraz>`
- **Model:** `llava:7b` via Ollama
- **Zależności:** Ollama + llava:7b

### 🧪 qwen-lab — Benchmarki modeli
- **Ścieżka:** `~/qwen-lab/`
- **Git:** lokalnie tylko (brak remote), zainicjowany
- **Uruchomienie:** `./run_benchmark.sh <model>` lub `./benchmark_tasks.sh`
- **Wyniki:** `results/` (gitignored, generowane)

### 🛒 scraper-product — Produktyzowany scraper (Upwork gig)
- **Ścieżka:** `~/scraper-product/`
- **Git:** lokalnie tylko (brak remote)
- **Uruchomienie:** `python3 pipeline/main.py --config config.yaml`
- **Wyjścia:** Excel + PDF raporty, Airtable, Slack/email, n8n workflow
- **Konfiguracja:** `config.yaml` + `.env` (secrets — nigdy do gita)

### 🌐 openwebui-setup — Open WebUI (UI dla Ollamy)
- **Ścieżka:** `~/openwebui-setup/`
- **Git:** NIE (venv 2.3 GB)
- **Uruchomienie:** `~/openwebui-setup/start.sh`
- **Port:** `http://localhost:3000`
- **Dane:** `~/openwebui-setup/data/`

### 🎮 MarioClone — Klon Mario (Python/pygame)
- **Ścieżka:** `~/MarioClone/`
- **Git:** lokalnie tylko (brak remote), zainicjowany
- **Uruchomienie:** `python3 main.py`

### 🎮 GodotMario — Klon Mario (Godot)
- **Ścieżka:** `~/GodotMario/`
- **Git:** lokalnie tylko (brak remote), zainicjowany
- **Uruchomienie:** Godot Engine → otwórz `project.godot`

### 🎮 IcyTower — Icy Tower (HTML/JS)
- **Ścieżka:** `~/IcyTower/`
- **Git:** lokalnie tylko (brak remote), zainicjowany
- **Uruchomienie:** otwórz `index.html` w przeglądarce

---

## Status GitHub (2026-06-01)

| Projekt | Git | Remote/GitHub | Synced |
|---------|-----|---------------|--------|
| qwen-agent | ✅ | ✅ `lolopaolo511-sudo/doomdoja-ai` | ✅ main=origin |
| qwen-scraper | ✅ | ❌ tylko lokalnie | — |
| qwen-rag | ✅ | ❌ tylko lokalnie | — |
| qwen-vision | ✅ | ❌ tylko lokalnie | — |
| qwen-lab | ✅ | ❌ tylko lokalnie | — |
| scraper-product | ✅ | ❌ tylko lokalnie | — |
| openwebui-setup | ❌ | ❌ | — |
| MarioClone | ✅ | ❌ tylko lokalnie | — |
| GodotMario | ✅ | ❌ tylko lokalnie | — |
| IcyTower | ✅ | ❌ tylko lokalnie | — |

**Odpowiedź: NIE — większość kodu jest TYLKO LOKALNIE.** Tylko `qwen-agent` jest na GitHubie.

---

## Szybkie komendy

```bash
# Start Ollamy
ollama serve

# Start Open WebUI
~/openwebui-setup/start.sh

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
