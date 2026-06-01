"""
eval_lite.py — eval harness bez Ollamy (tryb CI / mock).

Uruchamia te same zadania co runner.py, ale zamiast wywoływać Ollama
generuje deterministyczne odpowiedzi mockowe, które spełniają kryteria
expected_substring / expected_regex z tasks.yaml.

To testuje logikę oceniania (scoring), nie model.

Użycie:
    python3 evals/eval_lite.py                    # wszystkie zadania
    python3 evals/eval_lite.py --threshold 70     # próg pass-rate
    python3 evals/eval_lite.py --fail-some        # symuluj kilka fail (test bramki)
    CI=true python3 evals/eval_lite.py            # tryb CI (exit code 1 jeśli < threshold)

Zmienne środowiskowe:
    EVAL_PASS_THRESHOLD=70    próg procentowy (domyślnie 70)
    EVAL_FAIL_SOME=1          symuluje 2 faile (do testowania bramki CI)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

EVALS_DIR = Path(__file__).parent
REPORTS_DIR = EVALS_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

PASS_THRESHOLD = int(os.getenv("EVAL_PASS_THRESHOLD", "70"))


# ── Mock responses ────────────────────────────────────────────────────────────
# Każde zadanie dostaje odpowiedź, która CELOWO spełnia kryteria z tasks.yaml.
# Dzięki temu scoring logic jest testowany nawet bez Ollamy.
MOCK_RESPONSES: dict[str, str] = {
    "code_fizzbuzz": (
        "def fizzbuzz(n):\n"
        "    for i in range(1, n+1):\n"
        "        if i % 15 == 0: print('FizzBuzz')\n"
        "        elif i % 3 == 0: print('Fizz')\n"
        "        elif i % 5 == 0: print('Buzz')\n"
        "        else: print(i)\n"
    ),
    "code_palindrome": (
        "def is_palindrome(s):\n"
        "    return s == s[::-1]\n"
    ),
    "rag_python_dict": "Złożoność czasowa wyszukiwania w dict wynosi O(1) — hashing.",
    "rag_http_codes": "HTTP 429 oznacza Too Many Requests — klient przekroczył limit zapytań.",
    "reason_math": "80",
    "reason_word": "enihcam",
    "scrape_css_selector": "span.price",
    "vision_describe": "Na obrazie widoczny jest ekran z kodem źródłowym.",
}

# Odpowiedź domyślna dla nieznanych zadań (likely fail — celowo)
DEFAULT_MOCK = "mock response without specific content"


def load_tasks() -> list[dict]:
    cfg_path = EVALS_DIR / "tasks.yaml"
    import yaml
    return yaml.safe_load(cfg_path.read_text())["tasks"]


def score_task(task: dict, response: str) -> dict:
    """Ocenia odpowiedź wg kryteriów zadania. Identyczna logika jak runner.py."""
    passed = True
    fail_reasons = []

    if expected := task.get("expected_substring"):
        if expected.lower() not in response.lower():
            passed = False
            fail_reasons.append(f"substring miss: '{expected}'")

    if expected_re := task.get("expected_regex"):
        if not re.search(expected_re, response, re.IGNORECASE):
            passed = False
            fail_reasons.append(f"regex miss: '{expected_re}'")

    return {
        "id": task["id"],
        "category": task.get("category", "?"),
        "model": "mock",
        "status": "pass" if passed else "fail",
        "latency_s": 0.001,
        "tokens_per_s": 999.0,
        "tokens": len(response.split()),
        "response_snippet": response[:200],
        "fail_reasons": fail_reasons,
        "mock": True,
    }


def run_lite(tasks: list[dict], fail_some: bool = False) -> dict:
    results = []
    fail_injected = 0

    for task in tasks:
        # Zadania vision z obrazem — skip jeśli brak pliku
        if task.get("image_path"):
            p = Path(os.path.expanduser(task["image_path"]))
            if not p.exists():
                results.append({
                    "id": task["id"], "category": task.get("category", "?"),
                    "model": "mock", "status": "skipped",
                    "reason": f"image not found: {p}", "mock": True,
                })
                continue

        # Symuluj fail dla 2 zadań jeśli --fail-some (test bramki CI)
        if fail_some and fail_injected < 2 and task.get("category") == "reasoning":
            response = "totally wrong answer xyz"
            fail_injected += 1
        else:
            response = MOCK_RESPONSES.get(task["id"], DEFAULT_MOCK)

        result = score_task(task, response)
        results.append(result)

        icon = "✓" if result["status"] == "pass" else "✗"
        print(f"  [{result['id']}] {icon} {result['status']}", end="")
        if result["fail_reasons"]:
            print(f" — {'; '.join(result['fail_reasons'])}", end="")
        print()

    return results


def compute_pass_rate(results: list[dict]) -> float:
    counted = [r for r in results if r["status"] in ("pass", "fail")]
    if not counted:
        return 100.0
    passed = sum(1 for r in counted if r["status"] == "pass")
    return round(passed / len(counted) * 100, 1)


def save_report(results: list[dict], pass_rate: float, threshold: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "mode": "lite",
        "timestamp": datetime.now().isoformat(),
        "pass_rate": pass_rate,
        "threshold": threshold,
        "gate": "pass" if pass_rate >= threshold else "FAIL",
        "results": results,
    }
    path = REPORTS_DIR / f"eval_lite_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Eval lite (mock — bez Ollamy)")
    parser.add_argument("--threshold", type=int, default=PASS_THRESHOLD,
                        help=f"Minimalny pass-rate %% (domyślnie {PASS_THRESHOLD})")
    parser.add_argument("--fail-some", action="store_true",
                        help="Symuluj kilka fail (test bramki CI)")
    parser.add_argument("--category", help="Filtruj zadania po kategorii")
    args = parser.parse_args()

    tasks = load_tasks()
    if args.category:
        tasks = [t for t in tasks if t.get("category") == args.category]

    print(f"\n=== Eval LITE (mock, bez Ollamy) ===")
    print(f"Zadania: {len(tasks)}  |  Próg: {args.threshold}%")
    print("─" * 50)

    results = run_lite(tasks, fail_some=args.fail_some)
    pass_rate = compute_pass_rate(results)

    print("─" * 50)
    gate_ok = pass_rate >= args.threshold
    gate_str = "PASS ✓" if gate_ok else f"FAIL ✗ (próg {args.threshold}%)"
    print(f"Pass-rate: {pass_rate}%  |  Bramka: {gate_str}")

    report_path = save_report(results, pass_rate, args.threshold)
    print(f"Raport: {report_path}")

    # exit code 1 jeśli poniżej progu (CI używa tego do blokowania merge)
    return 0 if gate_ok else 1


if __name__ == "__main__":
    sys.exit(main())
