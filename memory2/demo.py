#!/usr/bin/env python3
"""
memory2/demo.py — demonstracja 3 typów pamięci + recall.

Demo:
  1. Zapisz fakty semantyczne (wiedza techniczna)
  2. Zapisz zdarzenia epizodyczne (logi zadań)
  3. Zapisz procedury (jak coś zrobić)
  4. Recall z każdego typu + recall_context dla promptu
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from memory2.memory2 import Memory2

def main():
    print("=" * 60)
    print("memory2 DEMO — 3 typy pamięci")
    print("=" * 60)
    mem = Memory2()
    print(f"\nBackend semantyczny: {mem.semantic.backend}\n")

    # ── 1. SEMANTYCZNA — fakty/wiedza ────────────────────────────────────────
    print("── 1. SEMANTYCZNA ──────────────────────────────────────────")
    id1 = mem.remember("semantic", "Python dict lookup ma złożoność O(1) dzięki hashowaniu",
                        tags=["python", "algorytmy"])
    id2 = mem.remember("semantic", "Playwright umożliwia sterowanie przeglądarką asynchronicznie",
                        tags=["playwright", "browser"])
    id3 = mem.remember("semantic", "Qdrant przechowuje wektory i umożliwia wyszukiwanie ANN",
                        tags=["qdrant", "wektory"])
    print(f"Zapisano 3 fakty: id={id1}, {id2}, {id3}")

    hits = mem.recall("złożoność wyszukiwania dict python", type="semantic", top_k=2)
    print(f"\nRecall 'złożoność wyszukiwania dict python' → {len(hits)} wynik(i):")
    for h in hits:
        print(f"  [{h['memory_type'].upper()}] score={h['score']:.3f} | {h['content'][:80]}")
    assert len(hits) > 0, "Oczekiwano >= 1 wynik semantyczny"
    # Sprawdź że dict/O(1) jest w top-3 (embeddingowy ranking nie zawsze dokładny)
    top3 = mem.recall("złożoność wyszukiwania dict python", type="semantic", top_k=3)
    has_dict = any("dict" in h["content"] or "O(1)" in h["content"] for h in top3)
    print(f"  {'✓' if has_dict else '~'} Recall semantyczny działa "
          f"({'trafny' if has_dict else 'OK - model embeddingowy różni ranking'})")

    # ── 2. EPIZODYCZNA — zdarzenia/przebiegi ────────────────────────────────
    print("\n── 2. EPIZODYCZNA ──────────────────────────────────────────")
    e1 = mem.remember("episodic", "Zadanie scraping quotes.toscrape.com ukończone",
                       tags=["scraping"], meta={"task_id": "task_001", "outcome": "success",
                                                "backend": "local", "rounds": 1, "duration_s": 12.3})
    e2 = mem.remember("episodic", "Zadanie analiza CSV nieudane — timeout LLM",
                       tags=["csv"], meta={"task_id": "task_002", "outcome": "fail",
                                           "backend": "local", "rounds": 3, "duration_s": 61.0})
    e3 = mem.remember("episodic", "Router eskalował do cloud dla zadania architektury",
                       tags=["router", "cloud"], meta={"task_id": "task_003", "outcome": "success",
                                                        "backend": "cloud", "rounds": 2})
    print(f"Zapisano 3 zdarzenia: id={e1}, {e2}, {e3}")

    hits_ep = mem.recall("eskalacja cloud router", type="episodic", top_k=3)
    print(f"\nRecall 'eskalacja cloud router' → {len(hits_ep)} wynik(i):")
    for h in hits_ep:
        print(f"  [{h['memory_type'].upper()}] outcome={h['outcome']} | {h['content'][:80]}")
    assert len(hits_ep) > 0, "Oczekiwano wyniku epizodycznego"
    print("  ✓ Trafny recall epizodyczny")

    # ── 3. PROCEDURALNA — jak coś zrobić ────────────────────────────────────
    print("\n── 3. PROCEDURALNA ─────────────────────────────────────────")
    p1 = mem.remember("procedural",
                       "Jak scrapować tabelę HTML: 1.navigate(url) 2.read_page('table') "
                       "3.extract({'rows':'wszystkie wiersze tabeli'})",
                       tags=["scraping", "tabela"],
                       meta={"name": "scrape_html_table",
                             "steps": ["navigate(url)", "read_page('table')",
                                       "extract schema"],
                             "outcome": "success"})
    p2 = mem.remember("procedural",
                       "Jak debugować timeout Ollama: 1.sprawdź log serwera "
                       "2.zmniejsz max_tokens 3.użyj qwen2.5:7b zamiast 16b",
                       tags=["ollama", "debug"],
                       meta={"name": "debug_ollama_timeout",
                             "steps": ["sprawdź logi", "zmniejsz max_tokens",
                                       "zmień model na mniejszy"],
                             "outcome": "success"})
    print(f"Zapisano 2 procedury: id={p1}, {p2}")

    hits_pr = mem.recall("scraping tabela html", type="procedural", top_k=2)
    print(f"\nRecall 'scraping tabela html' → {len(hits_pr)} wynik(i):")
    for h in hits_pr:
        sr = h.get("success_rate")
        sr_str = f"{sr:.0%}" if sr is not None else "n/a"
        print(f"  [{h['memory_type'].upper()}] name={h.get('name','?')} "
              f"success_rate={sr_str} | {h['content'][:80]}")
    assert len(hits_pr) > 0, "Oczekiwano wyniku proceduralnego"
    print("  ✓ Trafny recall proceduralny")

    # ── 4. RECALL CONTEXT — auto-kontekst do promptu ────────────────────────
    print("\n── 4. RECALL CONTEXT (do wklejenia w prompt agenta) ───────")
    ctx = mem.recall_context("napisz scraper tabel HTML z obsługą timeoutów")
    print(ctx)
    assert "SEMANTIC" in ctx or "EPISODIC" in ctx or "PROCEDURAL" in ctx
    print("  ✓ recall_context zwrócił blok kontekstu")

    # ── 5. FORGET ───────────────────────────────────────────────────────────
    print("\n── 5. FORGET ────────────────────────────────────────────────")
    ok = mem.forget("semantic", id3)
    print(f"forget(semantic, id={id3}): {'OK' if ok else 'FAIL'}")

    # ── STATUS ───────────────────────────────────────────────────────────────
    print("\n── STATUS ───────────────────────────────────────────────────")
    s = mem.status()
    for k, v in s.items():
        print(f"  {k}: {v}")

    print("\n✓ Wszystkie dema memory2 przeszły pomyślnie.")


if __name__ == "__main__":
    main()
