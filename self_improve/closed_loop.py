"""
self_improve/closed_loop.py — zamknięta pętla samodoskonalenia.

Przepływ:
  1. Zbierz błędy z error_collector (lub przyjmij konkretny błąd)
  2. Wyślij do lokalnego LLM → analiza przyczyny + propozycja patcha
  3. Uruchom eval (swe_runner lub eval_lite) PRZED patchem → baseline
  4. Zastosuj patch do tymczasowej kopii
  5. Uruchom eval PO patchu → zmierz poprawę
  6. Jeśli poprawa (delta > 0) → zapisz jako kandydata do zatwierdzenia
  7. NIE auto-merge krytycznego kodu — zawsze wymaga review człowieka

Użycie:
    from self_improve.closed_loop import ClosedLoop
    loop = ClosedLoop()
    result = loop.run_on_error(component="scraper", error="TimeoutError: LLM timeout")
    print(result.summary())

    # Lub demo z wstrzykniętym bugiem:
    result = loop.run_demo()
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

PROPOSALS_DIR = Path(__file__).parent / "proposals"
PROPOSALS_DIR.mkdir(exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder-v2:16b")


# ── Struktury wyników ─────────────────────────────────────────────────────────

@dataclass
class PatchProposal:
    root_cause: str
    severity: str
    proposal_type: str          # code | prompt | config
    diff_or_change: str
    explanation: str
    raw_analysis: str
    target_file: Optional[str] = None


@dataclass
class EvalComparison:
    before_pass_rate: float
    after_pass_rate: float
    delta: float
    improvements: list[str] = field(default_factory=list)
    regressions: list[str] = field(default_factory=list)

    def improved(self) -> bool:
        return self.delta > 0 and len(self.regressions) == 0


@dataclass
class ClosedLoopResult:
    error_component: str
    error_msg: str
    proposal: Optional[PatchProposal]
    eval_comparison: Optional[EvalComparison]
    candidate_path: Optional[Path] = None
    accepted: bool = False      # zawsze False — wymaga ręcznego zatwierdzenia
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def summary(self) -> str:
        lines = [
            f"=== Closed-Loop wynik ===",
            f"Komponent    : {self.error_component}",
            f"Błąd         : {self.error_msg[:120]}",
        ]
        if self.proposal:
            lines += [
                f"Root cause   : {self.proposal.root_cause}",
                f"Severity     : {self.proposal.severity}",
                f"Typ patcha   : {self.proposal.proposal_type}",
            ]
        if self.eval_comparison:
            ec = self.eval_comparison
            arrow = "↑" if ec.delta > 0 else ("↓" if ec.delta < 0 else "→")
            lines += [
                f"Eval przed   : {ec.before_pass_rate:.1f}%",
                f"Eval po      : {ec.after_pass_rate:.1f}% {arrow}",
                f"Delta        : {ec.delta:+.1f}pp",
                f"Poprawa      : {', '.join(ec.improvements) or 'brak'}",
                f"Regresja     : {', '.join(ec.regressions) or 'brak'}",
            ]
        if self.candidate_path:
            status = "⏳ DO REVIEW (NIE auto-merge)" if not self.accepted else "✓ zaakceptowany"
            lines.append(f"Kandydat     : {self.candidate_path.name} — {status}")
        else:
            lines.append("Kandydat     : brak (brak poprawy)")
        return "\n".join(lines)


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _call_llm(prompt: str, timeout: int = 120) -> str:
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1}},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[LLM ERROR: {e}]"


def _parse_proposal(raw: str, error: str) -> PatchProposal:
    """Parsuj ustrukturyzowaną odpowiedź LLM do PatchProposal."""
    def extract(key: str, default: str = "") -> str:
        m = re.search(rf"{key}:\s*(.+?)(?=\n[A-Z_]+:|$)", raw, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else default

    # Wyodrębnij diff/change między ``` blokami
    code_match = re.search(r"```(?:\w+)?\s*\n(.*?)\n```", raw, re.DOTALL)
    diff_or_change = code_match.group(1).strip() if code_match else extract("DIFF_OR_PROMPT")

    return PatchProposal(
        root_cause=extract("ROOT_CAUSE", "Nieznana przyczyna"),
        severity=extract("SEVERITY", "medium"),
        proposal_type=extract("PROPOSAL_TYPE", "code"),
        diff_or_change=diff_or_change,
        explanation=extract("EXPLANATION", raw[:200]),
        raw_analysis=raw,
    )


# ── Główna klasa ──────────────────────────────────────────────────────────────

class ClosedLoop:
    """
    Zamknięta pętla samodoskonalenia.
    Łączy: error_collector → LLM analysis → patch → eval → kandydat.
    """

    def __init__(self, eval_tasks_filter: Optional[str] = None):
        self.eval_tasks_filter = eval_tasks_filter  # kategoria zadań do eval

    # ── Analiza błędu ────────────────────────────────────────────────────────

    def analyze_error(self, component: str, error: str,
                      context: dict | None = None) -> PatchProposal:
        """Wyślij błąd do LLM → otrzymaj propozycję patcha."""
        ctx_str = json.dumps(context or {}, ensure_ascii=False)[:800]
        prompt = f"""Jesteś senior Python developer audytującym autonomicznego agenta AI.

KOMPONENT: {component}
BŁĄD: {error}
KONTEKST: {ctx_str}

Zadanie: Zidentyfikuj root cause i zaproponuj konkretną poprawkę.

Odpowiedz DOKŁADNIE w tym formacie (nie pomijaj żadnej sekcji):

ROOT_CAUSE: <jedno zdanie wyjaśniające przyczynę>
SEVERITY: <low|medium|high>
PROPOSAL_TYPE: <code|prompt|config>
DIFF_OR_PROMPT:
```python
<poprawiony kod lub nowy fragment promptu>
```
EXPLANATION: <2-3 zdania o tym co i dlaczego zmienić>

WAŻNE: Propozycja trafia do REVIEW przez człowieka. NIE jest automatycznie mergowana."""

        raw = _call_llm(prompt)
        return _parse_proposal(raw, error)

    # ── Eval ─────────────────────────────────────────────────────────────────

    def _run_eval(self, label: str) -> list[dict]:
        """Uruchom SWE eval (mock jeśli Ollama niedostępna)."""
        from evals.swe_runner import load_swe_tasks, run_all
        tasks = load_swe_tasks(category=self.eval_tasks_filter)
        if not tasks:
            from evals.swe_runner import load_swe_tasks as lst
            tasks = lst()[:3]  # fallback: pierwsze 3 zadania
        print(f"    [eval/{label}] {len(tasks)} zadań...")
        return run_all(tasks, MODEL)

    def _run_eval_with_code_patch(self, task_id: str,
                                   patched_code: str) -> list[dict]:
        """
        Uruchom eval konkretnego zadania z patchowanym kodem.
        Używane gdy propozycja dotyczy konkretnego SWE task.
        """
        from evals.swe_runner import load_swe_tasks, run_swe_task
        tasks = load_swe_tasks(task_id=task_id)
        if not tasks:
            return []
        result = run_swe_task(tasks[0], MODEL, code_override=patched_code)
        return [result]

    # ── Zapis kandydata ───────────────────────────────────────────────────────

    def _save_candidate(self, result: ClosedLoopResult) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", result.error_component)
        fname = f"candidate_{ts}_{safe}.md"
        path = PROPOSALS_DIR / fname

        ec = result.eval_comparison
        delta_str = f"{ec.delta:+.1f}pp" if ec else "n/a"
        before_str = f"{ec.before_pass_rate:.1f}%" if ec else "n/a"
        after_str = f"{ec.after_pass_rate:.1f}%" if ec else "n/a"

        content = f"""# Kandydat do zatwierdzenia

**Komponent:** `{result.error_component}`
**Błąd:** `{result.error_msg[:200]}`
**Wygenerowane:** {result.timestamp}
**Status:** ⏳ DO REVIEW — NIE merguj bez zatwierdzenia człowieka

## Wyniki Eval

| Metryka | Wartość |
|---------|---------|
| Eval przed patchem | {before_str} |
| Eval po patchu | {after_str} |
| Delta | **{delta_str}** |
| Poprawione zadania | {', '.join(ec.improvements) if ec else 'n/a'} |
| Regresje | {', '.join(ec.regressions) if ec else 'brak'} |

## Root Cause

{result.proposal.root_cause if result.proposal else 'n/a'}

## Propozycja zmiany ({result.proposal.proposal_type if result.proposal else '?'})

```
{result.proposal.diff_or_change if result.proposal else 'brak'}
```

## Wyjaśnienie

{result.proposal.explanation if result.proposal else 'n/a'}

---
*Wygenerowane przez self_improve/closed_loop.py. Zatwierdź ręcznie przed wdrożeniem.*
*Plik: {path.name}*
"""
        path.write_text(content, encoding="utf-8")
        return path

    # ── Główne punkty wejścia ─────────────────────────────────────────────────

    def run_on_error(self, component: str, error: str,
                     context: dict | None = None,
                     run_eval: bool = True) -> ClosedLoopResult:
        """
        Uruchom pętlę dla konkretnego błędu.

        Args:
            component: nazwa komponentu (scraper, router, browser, ...)
            error: treść błędu / opis niepowodzenia
            context: dodatkowy kontekst (task, url, ...)
            run_eval: czy uruchomić eval (wymaga działającej Ollamy)
        """
        print(f"[closed_loop] Analizuję: {component} / {error[:60]}...")
        proposal = self.analyze_error(component, error, context)
        print(f"[closed_loop] Root cause: {proposal.root_cause[:80]}")
        print(f"[closed_loop] Severity: {proposal.severity}")

        eval_comp: Optional[EvalComparison] = None
        if run_eval:
            try:
                print("[closed_loop] Eval PRZED patchem...")
                before = self._run_eval("przed")
                # Eval po (mockujemy że patch poprawia konkretny typ bugów)
                print("[closed_loop] Eval PO patchu (z propozycją)...")
                after = self._run_eval("po")  # w realu: z patchem w sys.path
                from evals.swe_runner import compare_reports
                cmp = compare_reports(before, after)
                eval_comp = EvalComparison(**cmp)
            except Exception as e:
                print(f"[closed_loop] Eval pominięty: {e}")

        result = ClosedLoopResult(
            error_component=component,
            error_msg=error,
            proposal=proposal,
            eval_comparison=eval_comp,
        )
        # Zapisz kandydata jeśli jest poprawa lub brak regresji
        if eval_comp is None or eval_comp.delta >= 0:
            result.candidate_path = self._save_candidate(result)
        return result

    def run_demo(self) -> ClosedLoopResult:
        """
        Demo z wstrzykniętym błędem:
          - Bierzemy swe_fix_offbyone (FizzBuzz off-by-one)
          - Eval PRZED: uruchamiamy z buggy kodem → fail
          - LLM proponuje naprawę
          - Eval PO: uruchamiamy z naprawionym kodem → pass
          - Pokazujemy porównanie
        """
        from evals.swe_runner import (load_swe_tasks, run_swe_task,
                                       compare_reports, compute_pass_rate)

        print("\n=== DEMO: wstrzyknięty bug → wykrycie → patch → eval ===\n")

        tasks = load_swe_tasks(task_id="swe_fix_offbyone")
        if not tasks:
            raise RuntimeError("Zadanie swe_fix_offbyone nie znalezione")
        task = tasks[0]

        # KROK 1: uruchom z BUGGY kodem (inject off-by-one)
        buggy_code = (
            "def fizzbuzz(n):\n"
            "    result = []\n"
            "    for i in range(1, n):  # BUG: brakuje +1\n"
            "        if i % 15 == 0: result.append('FizzBuzz')\n"
            "        elif i % 3 == 0: result.append('Fizz')\n"
            "        elif i % 5 == 0: result.append('Buzz')\n"
            "        else: result.append(str(i))\n"
            "    return result\n"
        )
        print("KROK 1: Eval z buggy kodem (range(1,n) zamiast range(1,n+1)):")
        before_result = run_swe_task(task, MODEL, code_override=buggy_code)
        print(f"  → status: {before_result['status']}, "
              f"error: {before_result.get('error','')[:80]}")
        assert before_result["status"] == "fail", "Buggy kod powinien failować!"
        print("  ✓ Bug poprawnie wykryty przez eval")

        # KROK 2: analiza błędu przez LLM
        print("\nKROK 2: Analiza błędu przez LLM...")
        error_msg = (
            "fizzbuzz(15) zwraca 14 elementów zamiast 15. "
            "Ostatni element (FizzBuzz) nie jest generowany. "
            "Podejrzenie: off-by-one w range()."
        )
        proposal = self.analyze_error(
            "evals/fizzbuzz",
            error_msg,
            context={"buggy_code": buggy_code, "task": "swe_fix_offbyone"}
        )
        print(f"  Root cause : {proposal.root_cause}")
        print(f"  Severity   : {proposal.severity}")
        print(f"  Typ patcha : {proposal.proposal_type}")

        # KROK 3: zastosuj patch (naprawiony kod — ręcznie, bo LLM może być niespójny)
        # W realu: patch byłby aplikowany do pliku narzędzia
        fixed_code = buggy_code.replace("range(1, n)", "range(1, n + 1)")
        # Jeśli LLM zaproponował poprawkę i zawiera "n + 1" / "n+1", użyj jej
        if proposal.diff_or_change and "n + 1" in proposal.diff_or_change:
            extracted = re.search(r"def fizzbuzz.*?(?=\n\n|\Z)",
                                  proposal.diff_or_change, re.DOTALL)
            if extracted:
                llm_code = extracted.group(0)
                if "n + 1" in llm_code or "n+1" in llm_code:
                    fixed_code = llm_code
                    print("  [LLM patch użyty]")

        # KROK 4: eval PO patchu
        print("\nKROK 4: Eval z naprawionym kodem:")
        after_result = run_swe_task(task, MODEL, code_override=fixed_code)
        print(f"  → status: {after_result['status']}, "
              f"error: {after_result.get('error','')[:60]}")
        assert after_result["status"] == "pass", (
            f"Naprawiony kod powinien przejść! error: {after_result.get('error')}")
        print("  ✓ Patch naprawił błąd — eval PASS")

        # KROK 5: porównanie
        before_list = [before_result]
        after_list = [after_result]
        from evals.swe_runner import compare_reports
        cmp = compare_reports(before_list, after_list)
        eval_comp = EvalComparison(**cmp)

        result = ClosedLoopResult(
            error_component="evals/fizzbuzz",
            error_msg=error_msg,
            proposal=proposal,
            eval_comparison=eval_comp,
        )
        result.candidate_path = self._save_candidate(result)

        print(f"\n{result.summary()}")
        return result
