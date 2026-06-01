#!/usr/bin/env python3
"""
Demo self-improve: wstrzykuje sztuczne błędy → analyzer wykrywa wzorzec →
generuje propozycję poprawki (markdown).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from error_collector import log_error, clear_errors, list_errors
from analyzer import run_analysis


def inject_synthetic_errors():
    """Symulujemy realistyczne błędy z różnych komponentów."""
    print("[demo] Wstrzykuję sztuczne błędy do errors.jsonl...\n")

    # Klaster 1: scraper rate limit
    for i in range(4):
        log_error(
            component="scraper",
            error="HTTPError: 429 Too Many Requests",
            context={"url": f"https://example.com/page{i}", "retry_count": 0},
            tool_call={"tool": "scrape_structured", "params": {"url": "https://example.com"}},
        )

    # Klaster 2: vision JSON parse
    for i in range(3):
        log_error(
            component="vision",
            error="JSONDecodeError: Expecting value: line 1 column 1",
            context={"model": "llava:7b", "raw_response": "Sure, here is the data:..."},
            tool_call={"tool": "vision_analyze", "params": {"mode": "extract_data"}},
        )

    # Klaster 3: pojedynczy
    log_error(
        component="prospecting",
        error="ValidationError: budget field cannot be empty",
        context={"job_id": "mock-099"},
    )

    print(f"  zalogowano {len(list_errors())} błędów.\n")


def main():
    clear_errors()
    inject_synthetic_errors()
    print("=" * 60)
    print("ANALIZA BŁĘDÓW")
    print("=" * 60)
    proposals = run_analysis(min_occurrences=1)
    print("\n" + "=" * 60)
    print(f"WYNIK: {len(proposals)} propozycji wygenerowanych")
    print("=" * 60)
    for p in proposals:
        print(f"\n--- {p.name} ---")
        print(p.read_text()[:600])
        print("...")


if __name__ == "__main__":
    main()
