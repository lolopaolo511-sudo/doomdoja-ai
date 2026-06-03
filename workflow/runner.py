"""
workflow/runner.py — CLI i parametryczne sterowanie workflow.

Obsługuje:
  --goal WARUNEK   warunek zakończenia (sprawdzany po każdej iteracji)
  --loop N         uruchamiaj workflow cyklicznie N razy (0 = nieskończoność)
  --budget TOKENY  twardy limit tokenów dla całego workflow
  --quarantine     wymuś tryb kwarantanny dla wszystkich agentów
  --dry-run        pokaż plan bez wykonania

Użycie jako biblioteka:
    from workflow.runner import run_workflow, WorkflowConfig

    cfg = WorkflowConfig(
        budget_tokens=5000,
        goal_condition="Wynik zawiera ranking z budżetami",
        loop=1,
    )
    result = run_workflow(my_workflow_fn, cfg=cfg)

Użycie CLI (python -m workflow.runner):
    python -m workflow.runner --help
    python -m workflow.runner --goal "zawiera JSON" --budget 8000 --loop 2
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .budget import WorkflowBudget, TokenBudgetExceeded
from .quarantine import quarantine as quarantine_ctx, is_quarantined

logger = logging.getLogger("qwen_agent.workflow.runner")


@dataclass
class WorkflowConfig:
    """Konfiguracja wykonania workflow."""
    budget_tokens: Optional[int] = None     # None = bez limitu
    goal_condition: Optional[str] = None    # None = brak warunku; string = LLM-check
    loop: int = 1                           # 0 = nieskończoność; N = N razy
    quarantine_all: bool = False            # wymuś quarantine na wszystkich agentów
    dry_run: bool = False                   # pokaż plan, nie wykonuj
    session_id: str = ""
    max_loop_interval_s: float = 0.0        # przerwa między iteracjami pętli


@dataclass
class RunResult:
    """Wynik wykonania workflow (pojedyncza lub wielokrotna iteracja)."""
    outputs: list[str]              # wyniki każdej iteracji
    iterations: int
    total_tokens: int
    elapsed_s: float
    completed_goal: bool            # goal_condition spełniony?
    budget_exceeded: bool
    errors: list[str]

    def final_output(self) -> str:
        return self.outputs[-1] if self.outputs else ""

    def report(self) -> str:
        lines = [
            "=== WorkflowRunner raport ===",
            f"Iteracje:  {self.iterations}",
            f"Tokeny:    {self.total_tokens}",
            f"Czas:      {self.elapsed_s:.1f}s",
            f"Cel:       {'SPEŁNIONY' if self.completed_goal else 'NIE sprawdzano / nie spełniony'}",
            f"Budżet:    {'PRZEKROCZONY' if self.budget_exceeded else 'OK'}",
        ]
        if self.errors:
            lines.append(f"Błędy ({len(self.errors)}):")
            for e in self.errors[:5]:
                lines.append(f"  - {e}")
        return "\n".join(lines)


def run_workflow(
    workflow_fn: Callable[..., str],
    *,
    cfg: Optional[WorkflowConfig] = None,
    **workflow_kwargs,
) -> RunResult:
    """
    Uruchom workflow_fn z konfiguracją sterowania.

    Args:
        workflow_fn: callable który przyjmuje budget= i session_id= i zwraca str
        cfg: WorkflowConfig; None = domyślna konfiguracja (jeden run, bez limitu)
        **workflow_kwargs: dodatkowe kwargs przekazywane do workflow_fn

    Returns:
        RunResult z wynikami wszystkich iteracji
    """
    cfg = cfg or WorkflowConfig()

    if cfg.dry_run:
        logger.info("[runner] DRY-RUN — nie wykonuję workflow")
        return RunResult(
            outputs=["[DRY-RUN]"], iterations=0, total_tokens=0,
            elapsed_s=0.0, completed_goal=False, budget_exceeded=False, errors=[],
        )

    budget = WorkflowBudget(total=cfg.budget_tokens, label="workflow-run") \
        if cfg.budget_tokens else None

    outputs: list[str] = []
    errors: list[str] = []
    total_tokens = 0
    completed_goal = False
    budget_exceeded = False
    global_start = time.monotonic()

    loop_count = 0
    max_loops = cfg.loop if cfg.loop > 0 else float("inf")

    while loop_count < max_loops:
        loop_count += 1
        logger.info(f"[runner] iteracja {loop_count}"
                    + (f"/{cfg.loop}" if cfg.loop > 0 else " (nieskończoność)"))

        try:
            kw = dict(workflow_kwargs)
            if budget:
                kw["budget"] = budget
            kw["session_id"] = cfg.session_id or f"run-{loop_count}"

            if cfg.quarantine_all:
                with quarantine_ctx():
                    output = workflow_fn(**kw)
            else:
                output = workflow_fn(**kw)

            outputs.append(str(output))

            if budget:
                total_tokens = budget.used

        except TokenBudgetExceeded as exc:
            logger.warning(f"[runner] Budżet tokenów przekroczony: {exc}")
            budget_exceeded = True
            errors.append(str(exc))
            break
        except Exception as exc:
            logger.error(f"[runner] Błąd iteracji {loop_count}: {exc}")
            errors.append(str(exc))
            outputs.append(f"[ERROR] {exc}")

        # ── Sprawdź warunek zakończenia ────────────────────────────────────────
        if cfg.goal_condition and outputs:
            if _check_goal(outputs[-1], cfg.goal_condition):
                completed_goal = True
                logger.info(f"[runner] Cel osiągnięty po {loop_count} iteracjach")
                break

        # ── Przerwa między iteracjami ─────────────────────────────────────────
        if loop_count < max_loops and cfg.max_loop_interval_s > 0:
            time.sleep(cfg.max_loop_interval_s)

    elapsed = time.monotonic() - global_start
    if budget:
        total_tokens = budget.used

    return RunResult(
        outputs=outputs,
        iterations=loop_count,
        total_tokens=total_tokens,
        elapsed_s=elapsed,
        completed_goal=completed_goal,
        budget_exceeded=budget_exceeded,
        errors=errors,
    )


def _check_goal(output: str, condition: str) -> bool:
    """Sprawdź warunek zakończenia przez mini-agenta."""
    try:
        from .primitives import agent
        result = agent(
            goal=(
                f"Does this output satisfy the condition: '{condition}'?\n"
                f"OUTPUT:\n{output[:1500]}\n\n"
                "Answer ONLY 'YES' or 'NO'."
            ),
            token_budget=150,
            force_local=True,
            agent_id="goal-checker",
        )
        return result.output.strip().upper().startswith("YES")
    except Exception as exc:
        logger.warning(f"[runner] goal check error: {exc}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m workflow.runner",
        description="Uruchamia workflow z konfiguracją sterowania.",
    )
    p.add_argument("--goal", metavar="WARUNEK",
                   help="Warunek zakończenia (LLM-sprawdzany po każdej iteracji)")
    p.add_argument("--loop", type=int, default=1, metavar="N",
                   help="Liczba iteracji (0=nieskończoność, domyślnie 1)")
    p.add_argument("--budget", type=int, default=None, metavar="TOKENY",
                   help="Twardy limit tokenów dla całego workflow")
    p.add_argument("--quarantine", action="store_true",
                   help="Wymuś tryb kwarantanny dla wszystkich agentów")
    p.add_argument("--dry-run", action="store_true",
                   help="Pokaż plan bez wykonania")
    p.add_argument("--session", default="", metavar="ID",
                   help="ID sesji (opcjonalne)")
    p.add_argument("--interval", type=float, default=0.0, metavar="SECS",
                   help="Przerwa między iteracjami pętli (sekundy)")
    return p


def config_from_args(args=None) -> WorkflowConfig:
    """Parsuj argumenty CLI i zwróć WorkflowConfig."""
    parser = _build_parser()
    ns = parser.parse_args(args)
    return WorkflowConfig(
        budget_tokens=ns.budget,
        goal_condition=ns.goal,
        loop=ns.loop,
        quarantine_all=ns.quarantine,
        dry_run=ns.dry_run,
        session_id=ns.session,
        max_loop_interval_s=ns.interval,
    )


if __name__ == "__main__":
    # Przykładowe uruchomienie — workflow wbudowane
    cfg = config_from_args()
    print(f"WorkflowConfig: budget={cfg.budget_tokens} loop={cfg.loop} "
          f"goal={cfg.goal_condition!r} quarantine={cfg.quarantine_all}")

    def example_workflow(budget=None, session_id="") -> str:
        from .primitives import agent
        r = agent(
            "Odpowiedz 'WORKFLOW DZIAŁA' i podaj datę.",
            budget=budget, session_id=session_id,
        )
        return r.output

    result = run_workflow(example_workflow, cfg=cfg)
    print(result.report())
    if result.outputs:
        print("\nOstatni wynik:\n", result.final_output())
