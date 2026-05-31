#!/usr/bin/env python3
"""
ROLA: Reviewer
Sprawdza kod, uruchamia testy, zwraca listę poprawek lub APPROVED.
"""

import re
import subprocess
import sys
from pathlib import Path
from llm import call_llm

SYSTEM_PROMPT = """Jesteś code reviewerem sprawdzającym kod Python.

Przejrzyj podany kod i zwróć:
1. APPROVED — jeśli kod jest poprawny, spełnia wymagania i testy przechodzą
2. Lista konkretnych poprawek — jeśli coś wymaga naprawy

Format odpowiedzi:
STATUS: APPROVED lub NEEDS_FIXES

ISSUES:
- [CRITICAL] Opis krytycznego błędu
- [WARNING] Opis potencjalnego problemu
- [STYLE] Sugestia stylistyczna (opcjonalna)

FIXES:
Konkretne instrukcje co zmienić (jeśli STATUS=NEEDS_FIXES)
"""


def run_tests(work_dir: Path) -> tuple[bool, str]:
    """Uruchamia pytest i zwraca (sukces, output)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", "--no-header"],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def review(plan: dict, code_files: dict[str, str], test_output: str) -> dict:
    """Przegląda kod i wyniki testów, zwraca decyzję."""
    code_block = "\n\n".join(
        f"### {fname} ###\n```python\n{code}\n```"
        for fname, code in code_files.items()
    )

    prompt = SYSTEM_PROMPT
    prompt += f"\n\nCel zadania: {plan.get('goal', '?')}"
    prompt += f"\n\nKod do przeglądu:\n{code_block}"
    prompt += f"\n\nWyniki testów:\n```\n{test_output or '(testy nie uruchomione)'}\n```"

    response = call_llm(prompt, temperature=0.1)

    approved = "APPROVED" in response.upper() and "NEEDS_FIXES" not in response.upper()

    issues = []
    for line in response.splitlines():
        if line.strip().startswith("- ["):
            issues.append(line.strip())

    fixes_match = re.search(r'FIXES:(.*?)$', response, re.DOTALL | re.IGNORECASE)
    fixes = fixes_match.group(1).strip() if fixes_match else ""

    return {
        "approved": approved,
        "issues": issues,
        "fixes": fixes,
        "raw": response,
    }
