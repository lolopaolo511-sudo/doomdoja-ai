"""
evals/swe_runner.py — SWE-bench-style runner: generuj kod + uruchom testy.

Każde zadanie:
  1. Model generuje kod na podstawie promptu
  2. Kod + test_code są wykonywane w izolowanym subprocess
  3. Wynik: pass/fail + szczegóły błędu jeśli fail

Używa lokalnego Ollama (bez chmury). Dobry do mierzenia regresji/postępu.

Użycie:
    python3 evals/swe_runner.py                        # wszystkie SWE zadania
    python3 evals/swe_runner.py --task swe_fix_offbyone
    python3 evals/swe_runner.py --model qwen2.5-coder:7b
    python3 evals/swe_runner.py --code-override "def fizzbuzz(n): ..."  # test gotowego kodu
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import yaml

EVALS_DIR = Path(__file__).parent
REPORTS_DIR = EVALS_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


def load_swe_tasks(task_id: Optional[str] = None,
                   category: Optional[str] = None) -> list[dict]:
    path = EVALS_DIR / "swe_tasks.yaml"
    tasks = yaml.safe_load(path.read_text())["tasks"]
    if task_id:
        tasks = [t for t in tasks if t["id"] == task_id]
    if category:
        tasks = [t for t in tasks if t.get("category") == category]
    return tasks


def _call_llm(prompt: str, model: str, timeout: int = 90) -> str:
    """Wywołaj lokalny model, zwróć wygenerowany kod."""
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0}},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"# LLM ERROR: {e}"


def _extract_code(response: str) -> str:
    """Wyodrębnij blok kodu z odpowiedzi LLM (markdown lub raw)."""
    # Spróbuj blok ```python ... ```
    m = re.search(r"```(?:python)?\s*\n(.*?)\n```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Spróbuj blok ``` ... ```
    m = re.search(r"```(.*?)```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Zwróć jako-jest jeśli zawiera def / class
    if "def " in response or "class " in response:
        return response.strip()
    return response.strip()


def _run_code_with_tests(code: str, test_code: str,
                          timeout: int = 10) -> dict:
    """
    Uruchom kod + testy w izolowanym subprocess.
    Zwraca {"passed": bool, "error": str|None, "stdout": str}.
    """
    full_script = f"{code}\n\n# === TESTS ===\n{test_code}\nprint('__TESTS_PASSED__')\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                     delete=False, encoding="utf-8") as f:
        f.write(full_script)
        script_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=timeout,
        )
        passed = "__TESTS_PASSED__" in result.stdout
        error = None
        if not passed:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            error = stderr or stdout or "Testy nie zwróciły __TESTS_PASSED__"
        return {
            "passed": passed,
            "error": error,
            "stdout": result.stdout[:500],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": f"Timeout ({timeout}s)", "stdout": ""}
    except Exception as e:
        return {"passed": False, "error": str(e), "stdout": ""}
    finally:
        Path(script_path).unlink(missing_ok=True)


def run_swe_task(task: dict, model: str,
                 code_override: Optional[str] = None) -> dict:
    """
    Uruchom jedno SWE zadanie.

    Args:
        task: definicja zadania z swe_tasks.yaml
        model: nazwa modelu Ollama
        code_override: gotowy kod (pomiń generowanie przez LLM)
    Returns:
        Wynik z polami: id, status, passed, latency_s, code, error
    """
    t0 = time.monotonic()

    if code_override:
        generated_raw = code_override
        code = _extract_code(code_override)
        latency = 0.0
    else:
        generated_raw = _call_llm(task["prompt"], model,
                                   timeout=task.get("timeout_s", 90))
        latency = time.monotonic() - t0
        code = _extract_code(generated_raw)

    test_result = _run_code_with_tests(code, task["test_code"])

    status = "pass" if test_result["passed"] else "fail"
    return {
        "id": task["id"],
        "category": task.get("category", "?"),
        "description": task.get("description", ""),
        "model": model if not code_override else "code_override",
        "status": status,
        "passed": test_result["passed"],
        "latency_s": round(latency, 2),
        "error": test_result.get("error"),
        "code_snippet": code[:300],
    }


def run_all(tasks: list[dict], model: str,
            code_override: Optional[str] = None) -> list[dict]:
    results = []
    for task in tasks:
        result = run_swe_task(task, model, code_override=code_override)
        icon = "✓" if result["status"] == "pass" else "✗"
        print(f"  [{result['id']}] {icon} {result['status']}"
              f"  ({result['latency_s']:.1f}s)", end="")
        if result["error"]:
            print(f" — {result['error'][:80]}", end="")
        print()
        results.append(result)
    return results


def compute_pass_rate(results: list[dict]) -> float:
    counted = [r for r in results if r["status"] in ("pass", "fail")]
    if not counted:
        return 100.0
    return round(sum(1 for r in counted if r["status"] == "pass") / len(counted) * 100, 1)


def save_report(results: list[dict], label: str = "") -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pass_rate = compute_pass_rate(results)
    report = {
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "pass_rate": pass_rate,
        "results": results,
    }
    path = REPORTS_DIR / f"swe_{ts}{'_' + label if label else ''}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return path


def compare_reports(before: list[dict], after: list[dict]) -> dict:
    """Porównaj wyniki przed i po patchu."""
    before_map = {r["id"]: r["status"] for r in before}
    after_map = {r["id"]: r["status"] for r in after}
    improvements = [tid for tid, s in after_map.items()
                    if s == "pass" and before_map.get(tid) == "fail"]
    regressions = [tid for tid, s in after_map.items()
                   if s == "fail" and before_map.get(tid) == "pass"]
    return {
        "before_pass_rate": compute_pass_rate(before),
        "after_pass_rate": compute_pass_rate(after),
        "delta": compute_pass_rate(after) - compute_pass_rate(before),
        "improvements": improvements,
        "regressions": regressions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SWE-bench mini runner")
    parser.add_argument("--task", help="ID konkretnego zadania")
    parser.add_argument("--category", help="Kategoria zadań")
    parser.add_argument("--model", default="deepseek-coder-v2:16b")
    parser.add_argument("--code-override", help="Gotowy kod (pomiń LLM)")
    args = parser.parse_args()

    tasks = load_swe_tasks(task_id=args.task, category=args.category)
    if not tasks:
        print(f"Nie znaleziono zadań (task={args.task}, cat={args.category})")
        return 1

    print(f"\n=== SWE Runner | model={args.model} | zadań={len(tasks)} ===")
    results = run_all(tasks, args.model, code_override=args.code_override)
    rate = compute_pass_rate(results)
    print(f"\nPass-rate: {rate}%")
    path = save_report(results, label=args.model.replace(":", "_"))
    print(f"Raport: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
