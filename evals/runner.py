"""
Eval runner — puszcza zestaw zadań przez model(e) i ocenia (pass/fail + metryki).

Metryki:
  - pass/fail (oczekiwany substring / regex)
  - latency (s)
  - tokens/sec (estymowane przez Ollama eval_count / total_duration)
  - quality score (1-10 — przez LLM judge, opcjonalnie)
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import yaml

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EVALS_DIR = Path(__file__).parent
REPORTS_DIR = EVALS_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def load_tasks() -> list[dict]:
    cfg = yaml.safe_load((EVALS_DIR / "tasks.yaml").read_text())
    return cfg["tasks"]


def run_task(task: dict, model: str) -> dict:
    prompt = task["prompt"]
    payload = {"model": model, "prompt": prompt, "stream": False,
               "options": {"temperature": 0.0}}
    if image := task.get("image_path"):
        p = Path(os.path.expanduser(image))
        if p.exists():
            payload["images"] = [base64.b64encode(p.read_bytes()).decode()]
        else:
            return {"id": task["id"], "model": model, "status": "skipped",
                    "reason": f"image not found: {p}"}

    t0 = time.monotonic()
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/generate", json=payload,
                       timeout=task.get("timeout_s", 60))
        r.raise_for_status()
        data = r.json()
        response = data.get("response", "").strip()
        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 1)
        tok_per_s = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns else 0
    except Exception as e:
        return {"id": task["id"], "model": model, "status": "error",
                "error": str(e), "latency_s": time.monotonic() - t0}

    latency = time.monotonic() - t0

    # Evaluation
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
        "model": model,
        "status": "pass" if passed else "fail",
        "latency_s": round(latency, 2),
        "tokens_per_s": round(tok_per_s, 1),
        "tokens": eval_count,
        "response_snippet": response[:200],
        "fail_reasons": fail_reasons,
    }


def run_suite(models: list[str], tasks: Optional[list[dict]] = None) -> dict:
    tasks = tasks or load_tasks()
    results = []
    for model in models:
        print(f"\n=== Model: {model} ===")
        for task in tasks:
            print(f"  [{task['id']}]... ", end="", flush=True)
            res = run_task(task, model)
            results.append(res)
            status = res["status"]
            icon = "✓" if status == "pass" else ("⚠" if status == "skipped" else "✗")
            print(f"{icon} {status} ({res.get('latency_s', '?')}s, "
                  f"{res.get('tokens_per_s', '?')} tok/s)")
            if res.get("fail_reasons"):
                print(f"      → {'; '.join(res['fail_reasons'])}")

    summary = summarize(results)
    return {"results": results, "summary": summary,
            "timestamp": datetime.now().isoformat()}


def summarize(results: list[dict]) -> dict:
    by_model: dict[str, dict] = {}
    for r in results:
        m = r["model"]
        by_model.setdefault(m, {"pass": 0, "fail": 0, "skipped": 0, "error": 0,
                                "total_latency": 0, "total_tokens": 0})
        s = r["status"]
        by_model[m][s] = by_model[m].get(s, 0) + 1
        by_model[m]["total_latency"] += r.get("latency_s", 0)
        by_model[m]["total_tokens"] += r.get("tokens", 0)

    for m, d in by_model.items():
        total = d["pass"] + d["fail"]
        d["pass_rate"] = round(d["pass"] / total * 100, 1) if total else 0
        d["avg_latency"] = round(d["total_latency"] / max(1, total + d["error"]), 2)
        d["avg_tok_per_s"] = round(d["total_tokens"] / max(1, d["total_latency"]), 1)
    return by_model


def save_report(report: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"eval_{ts}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    # also save markdown table
    md_path = REPORTS_DIR / f"eval_{ts}.md"
    lines = [f"# Eval report — {ts}\n",
             "| Model | Pass rate | Pass | Fail | Skipped | Avg latency | Avg tok/s |",
             "|-------|-----------|------|------|---------|-------------|-----------|"]
    for m, s in report["summary"].items():
        lines.append(f"| `{m}` | **{s['pass_rate']}%** | {s['pass']} | {s['fail']} | "
                     f"{s['skipped']} | {s['avg_latency']}s | {s['avg_tok_per_s']} |")
    lines.append("\n## Szczegóły\n")
    for r in report["results"]:
        icon = "✓" if r["status"] == "pass" else ("⚠" if r["status"] == "skipped" else "✗")
        lines.append(f"- {icon} `{r['id']}` / `{r['model']}` — {r['status']}"
                     f" ({r.get('latency_s', '?')}s)")
        if r.get("fail_reasons"):
            lines.append(f"  - **fail:** {'; '.join(r['fail_reasons'])}")
    md_path.write_text("\n".join(lines))
    return md_path


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=["deepseek-coder-v2:16b"],
                   help="Modele do testowania (Ollama tag)")
    p.add_argument("--category", help="Filtruj po kategorii")
    args = p.parse_args()

    tasks = load_tasks()
    if args.category:
        tasks = [t for t in tasks if t.get("category") == args.category]

    report = run_suite(args.models, tasks)
    md_path = save_report(report)
    print(f"\nRaport: {md_path}")
    print(f"JSON:   {md_path.with_suffix('.json')}")
    print("\n=== PODSUMOWANIE ===")
    for m, s in report["summary"].items():
        print(f"  {m}: {s['pass_rate']}% pass | {s['pass']}/{s['pass']+s['fail']} | "
              f"avg {s['avg_latency']}s")
