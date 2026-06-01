"""
Analyzer — używa lokalnego LLM (Ollama) do analizy zebranych błędów
i proponowania poprawek (diff) do narzędzi/promptów.

Propozycje zapisywane do proposals/ jako .patch + .md (do review).
NIE auto-merge — to jest tylko propozycja dla człowieka.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from error_collector import list_errors

PROPOSALS_DIR = Path(__file__).parent / "proposals"
PROPOSALS_DIR.mkdir(exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder-v2:16b")


def _call_llm(prompt: str, timeout: int = 120) -> str:
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1}},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["response"].strip()
    except Exception as e:
        return f"[LLM ERROR: {e}]"


def cluster_errors(errors: list[dict]) -> dict[str, list[dict]]:
    """Grupuj po (component, error type)."""
    clusters: dict[str, list[dict]] = defaultdict(list)
    for e in errors:
        # extract error type (first word/exception name)
        m = re.match(r"^([A-Za-z]+(?:Error|Exception)?)", e.get("error", ""))
        err_type = m.group(1) if m else "Unknown"
        key = f"{e.get('component', '?')}::{err_type}"
        clusters[key].append(e)
    return dict(clusters)


def analyze_cluster(cluster_key: str, errors: list[dict]) -> dict:
    """Wyślij klaster błędów do LLM, dostań propozycję poprawki."""
    sample = errors[:5]
    prompt = f"""Jesteś senior Python developer audytującym agenta.

KLASTER BŁĘDÓW: {cluster_key}
WYSTĄPIEŃ: {len(errors)}

PRZYKŁADY:
{json.dumps(sample, ensure_ascii=False, indent=2)[:3000]}

ZADANIE:
1. Zidentyfikuj root cause (1 zdanie).
2. Zaproponuj konkretną poprawkę kodu LUB promptu.
3. Jeśli to bug w narzędziu → podaj diff (unified format).
4. Jeśli to problem w prompcie → podaj nowy fragment promptu.

WAŻNE: Propozycja idzie do review przez człowieka. NIE auto-merge.

Odpowiedz w formacie:
ROOT_CAUSE: <jedno zdanie>
SEVERITY: <low|medium|high>
PROPOSAL_TYPE: <code|prompt|config>
DIFF_OR_PROMPT:
```
<zaproponowana zmiana>
```
EXPLANATION: <2-3 zdania>"""

    response = _call_llm(prompt)
    return {
        "cluster": cluster_key,
        "occurrences": len(errors),
        "analysis": response,
        "sample_errors": [e["error"] for e in sample],
    }


def save_proposal(analysis: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", analysis["cluster"])
    fname = f"proposal_{ts}_{safe_key}.md"
    path = PROPOSALS_DIR / fname
    content = f"""# Propozycja poprawki

**Klaster:** `{analysis['cluster']}`
**Wystąpień:** {analysis['occurrences']}
**Wygenerowane:** {datetime.now().isoformat()}
**Status:** ⏳ DO REVIEW (nie auto-mergowane)

## Przykładowe błędy
{chr(10).join(f"- `{e}`" for e in analysis['sample_errors'][:3])}

## Analiza LLM

{analysis['analysis']}

---
*Wygenerowane przez self_improve/analyzer.py. Zatwierdź ręcznie przed wdrożeniem.*
"""
    path.write_text(content)
    return path


def run_analysis(min_occurrences: int = 1) -> list[Path]:
    errors = list_errors()
    if not errors:
        print("[analyzer] Brak błędów do analizy.")
        return []

    clusters = cluster_errors(errors)
    print(f"[analyzer] Znaleziono {len(clusters)} klastrów błędów:")
    for k, v in clusters.items():
        print(f"  • {k}: {len(v)} wystąpień")

    proposals = []
    for k, v in clusters.items():
        if len(v) < min_occurrences:
            continue
        print(f"[analyzer] Analizuję klaster: {k}...")
        analysis = analyze_cluster(k, v)
        path = save_proposal(analysis)
        proposals.append(path)
        print(f"  → {path.name}")

    return proposals


if __name__ == "__main__":
    paths = run_analysis()
    print(f"\n[analyzer] Wygenerowano {len(paths)} propozycji w {PROPOSALS_DIR}")
