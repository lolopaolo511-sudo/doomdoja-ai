# qwen-agent — lokalny system agentowy

Rozbudowany lokalny system AI oparty na Ollama + deepseek-coder-v2:16b.
Wszystko działa offline, na `127.0.0.1`, bez wysyłania danych na zewnątrz.

## Status etapów

| # | Etap | Status | Artefakt | Uruchomienie |
|---|------|--------|----------|-------------|
| 2 | Web Dashboard | ✅ DONE | `dashboard/` | `bash dashboard/start.sh` |
| 3 | RAG (kod + docs) | ✅ DONE | `~/qwen-rag/` | `python3 ~/qwen-rag/query.py "pytanie"` |
| 4 | Vision / OCR | ✅ DONE | `~/qwen-vision/` | `python3 ~/qwen-vision/vision_cli.py obraz.png` |
| 5 | Pamięć długoterminowa | ✅ DONE | `memory.py` | `python3 memory_cli.py recall "pytanie"` |
| 7 | Automatyzacja GitHub | ✅ DONE | `github/` | `python3 github/git_agent.py auto ...` |
| 8 | Multi-agent | ✅ DONE | `multiagent/` | `python3 multiagent/orchestrator.py "zadanie"` |

---

## Etap 2 — Web Dashboard

Panel w przeglądarce do nadzoru agenta.

```bash
bash ~/qwen-agent/dashboard/start.sh
# → http://127.0.0.1:8080
```

**Co pokazuje:**
- Kolejka zadań (pending / done / failed) z treścią
- Status modeli Ollama (live check)
- Logi (ostatnie 80 linii, auto-refresh co 15s)
- Formularz tworzenia nowych zadań
- Przycisk uruchomienia agenta na wskazanym repo

**API:** `GET /api/status`, `GET /api/logs`, `POST /task/create`

---

## Etap 3 — RAG (Retrieval-Augmented Generation)

Semantyczne wyszukiwanie po zaindeksowanym kodzie i dokumentach.

```bash
# Zaindeksuj katalog
python3 ~/qwen-rag/ingest.py ~/qwen-scraper

# Zapytaj o kod
python3 ~/qwen-rag/query.py "jak działa ekstrakcja LLM?"

# Tylko retrieval (bez LLM)
python3 ~/qwen-rag/query.py "playwright scraper" --no-llm --top-k 3
```

**Modele:** `nomic-embed-text` (embeddingi) + `deepseek-coder-v2:16b` (odpowiedź)  
**Baza:** `~/qwen-rag/chroma_db/` (ChromaDB)  
**Import w agencie:** `from rag_tool import RAGTool`

---

## Etap 4 — Vision / OCR (Multimodal)

Analiza obrazów lokalnym modelem `llava:7b`.

```bash
# Opis obrazu
python3 ~/qwen-vision/vision_cli.py obraz.png

# OCR — wyciągnij tekst
python3 ~/qwen-vision/vision_cli.py obraz.png --ocr

# Wyciągnij dane jako JSON
python3 ~/qwen-vision/vision_cli.py screenshot.png --extract-data

# Własne pytanie
python3 ~/qwen-vision/vision_cli.py diagram.png --prompt "Co oznacza ta architektura?"

# Import w agencie
# from vision_tool import VisionTool
# vt = VisionTool()
# print(vt.ocr("screenshot.png"))
```

---

## Etap 5 — Pamięć długoterminowa

Trwała pamięć między sesjami (SQLite + cosine similarity na embeddingach).

```bash
# Zapamiętaj fakt
python3 ~/qwen-agent/memory_cli.py remember "Projekt X używa Poetry" --tags poetry project

# Przypomnij pasujące fakty (nowa sesja!)
python3 ~/qwen-agent/memory_cli.py recall "jak zarządzamy zależnościami?"

# Lista wszystkich wspomnień
python3 ~/qwen-agent/memory_cli.py list

# Statystyki
python3 ~/qwen-agent/memory_cli.py stats
```

**Baza:** `~/qwen-agent/agent_memory.db`  
**Integracja:** `agent_runner.py` automatycznie injectuje kontekst z pamięci przed zadaniem i zapisuje wynik po wykonaniu.

---

## Etap 7 — Automatyzacja GitHub

Tworzenie branchy, commitów, pushów i PR przez skrypt.

```bash
# Pełny pipeline
python3 ~/qwen-agent/github/git_agent.py auto \
  --repo /ścieżka/repo \
  --branch "feat/nowa-funkcja" \
  --message "feat: opis zmian" \
  --title "Tytuł PR"

# Poszczególne kroki
python3 ~/qwen-agent/github/git_agent.py branch --repo . --name "fix/blad"
python3 ~/qwen-agent/github/git_agent.py commit --repo . --message "fix: naprawa" --all
python3 ~/qwen-agent/github/git_agent.py push   --repo .
python3 ~/qwen-agent/github/git_agent.py pr     --repo . --title "Fix buga X"
```

**Push i PR przez API** wymagają tokena:
```bash
export GITHUB_TOKEN=ghp_TWÓJ_TOKEN
```
Bez tokena: branch + commit + opis PR działają lokalnie.  
Szczegóły: `github/SETUP.md`

---

## Etap 8 — Multi-agent (Planner + Coder + Reviewer)

Orkiestrator z trzema rolami LLM rozwiązujący zadania programistyczne end-to-end.

```bash
python3 ~/qwen-agent/multiagent/orchestrator.py \
  "Napisz moduł cache.py z LRU cache i testy pytest" \
  --work-dir /tmp/moje-zadanie \
  --max-rounds 2
```

**Role:**
- `planner.py` — rozkłada zadanie na 4-7 kroków (JSON)
- `coder.py` — implementuje każdy krok (krok po kroku, z kontekstem)
- `reviewer.py` — uruchamia `pytest` + przegląda kod LLM → APPROVED / NEEDS_FIXES
- `orchestrator.py` — spinacz z pętlą poprawek (domyślnie 2 rundy)

**Wynik:** katalog roboczy z plikami + `multiagent_report.json`

---

## Modele Ollama

| Model | Rozmiar | Rola |
|-------|---------|------|
| `deepseek-coder-v2:16b` | 8.9 GB | Główny LLM (kod, planner, reviewer) |
| `qwen2.5-coder:14b` | 9.0 GB | Alternatywny LLM |
| `qwen2.5-coder:7b` | 4.7 GB | Szybki LLM |
| `nomic-embed-text` | ~274 MB | Embeddingi (RAG + pamięć) |
| `llava:7b` | ~4.7 GB | Vision / OCR |

## Struktura

```
~/qwen-agent/
├── agent_runner.py       # Główna pętla agentowa (zadanie→aider→pytest→commit)
├── memory.py             # Trwała pamięć (etap 5)
├── memory_cli.py         # CLI do pamięci
├── dashboard/            # Web dashboard (etap 2)
│   ├── app.py
│   ├── start.sh
│   └── templates/index.html
├── github/               # GitHub automation (etap 7)
│   ├── git_agent.py
│   └── SETUP.md
├── multiagent/           # Multi-agent (etap 8)
│   ├── orchestrator.py
│   ├── planner.py
│   ├── coder.py
│   ├── reviewer.py
│   └── llm.py
└── tasks/
    ├── pending/          # Zadania do wykonania
    ├── done/             # Ukończone
    └── failed/           # Nieudane

~/qwen-rag/               # RAG (etap 3)
├── ingest.py
├── query.py
├── rag_tool.py
└── chroma_db/

~/qwen-vision/            # Vision/OCR (etap 4)
├── vision_cli.py
├── vision_tool.py
└── make_sample.py
```

## Status końcowy

Wszystkie 6 etapów ukończone. Repo na: https://github.com/lolopaolo511-sudo/doomdoja-ai

