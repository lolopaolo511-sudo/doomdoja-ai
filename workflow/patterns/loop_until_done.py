"""
workflow/patterns/loop_until_done.py

Wzorzec: ITERUJ AŻ WARUNEK SPEŁNIONY

Agent iteruje nad zadaniem, dostając feedback z poprzedniej iteracji,
dopóki warunek ukończenia nie jest spełniony lub nie wyczerpie się
maksymalna liczba iteracji (twardy hard stop).

Warunek ukończenia może być:
  - callable(output: str) -> bool  — deterministyczna funkcja (szybka)
  - str                            — warunek opisany naturalnym językiem
                                     (sprawdzany przez mini-agenta)

Użycie:
    from workflow.patterns import loop_until_done

    # Wariant 1: deterministyczny warunek
    result = loop_until_done(
        task="Napisz funkcję Python sortującą listę. Uwzględnij edge cases.",
        done_condition=lambda out: "def " in out and "return" in out,
        max_iterations=3,
    )

    # Wariant 2: LLM-sprawdzany warunek
    result = loop_until_done(
        task="Napisz podsumowanie ogłoszenia freelance",
        done_condition="Podsumowanie zawiera: budżet, wymagane technologie i deadline",
        max_iterations=4,
    )

    print(result.final_output)
    print(f"Iterations: {result.iterations}/{result.max_iterations}")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Union

from ..primitives import agent, AgentResult
from ..budget import WorkflowBudget

logger = logging.getLogger("qwen_agent.workflow.loop")

DoneCondition = Union[Callable[[str], bool], str]


@dataclass
class LoopResult:
    results: list[AgentResult]
    iterations: int
    max_iterations: int
    completed: bool               # True = warunek spełniony; False = hit max_iter
    final_output: str

    @property
    def hit_limit(self) -> bool:
        return not self.completed

    def report(self) -> str:
        status = "UKOŃCZONE" if self.completed else f"HIT LIMIT ({self.max_iterations})"
        lines = [f"=== loop_until_done: {status} ==="]
        for i, r in enumerate(self.results, 1):
            lines.append(f"  Iter {i}: {r.backend}/{r.model} | "
                         f"{r.tokens_used}tok | {r.elapsed_s:.1f}s | "
                         f"{'OK' if r.ok else f'ERR:{r.error}'}")
        total_tok = sum(r.tokens_used for r in self.results)
        lines.append(f"  Łącznie: {total_tok} tokenów, {self.iterations} iteracji")
        return "\n".join(lines)


_CHECKER_SYSTEM = (
    "You are a completion checker. Evaluate if output meets the condition. "
    "Answer ONLY 'YES' or 'NO'."
)


def loop_until_done(
    task: str,
    done_condition: DoneCondition,
    *,
    context: str = "",
    max_iterations: int = 5,
    token_budget_per_iteration: int = 2000,
    checker_token_budget: int = 200,
    budget: Optional[WorkflowBudget] = None,
    force_local: bool = False,
    force_cloud: bool = False,
    session_id: str = "",
    feedback_template: str = (
        "Poprzednia próba nie spełniła warunku. Popraw:\n\n"
        "POPRZEDNIA ODPOWIEDŹ:\n{prev_output}\n\n"
        "KONTEKST:\n{context}"
    ),
) -> LoopResult:
    """
    Iteruj aż warunek ukończenia spełniony lub max_iterations wyczerpane.

    Args:
        task: zadanie do wykonania (cel agenta per iteracja)
        done_condition: warunek ukończenia:
                        - callable(str) -> bool: deterministyczna funkcja
                        - str: opis warunku sprawdzany przez mini-agenta
        context: bazowy kontekst (dostępny w każdej iteracji)
        max_iterations: twardy limit — ZAWSZE zatrzymuje po tym
        token_budget_per_iteration: limit tokenów per iteracja roboczy
        checker_token_budget: limit tokenów mini-agenta sprawdzającego warunek
        budget: WorkflowBudget (opcjonalny)
        force_local: wymuś model lokalny
        force_cloud: wymuś cloud
        session_id: id sesji
        feedback_template: szablon kontekstu dla kolejnych iteracji

    Returns:
        LoopResult z listą wyników, liczbą iteracji i statusem
    """
    results: list[AgentResult] = []
    current_context = context

    for i in range(max_iterations):
        logger.info(f"[loop] iteracja {i+1}/{max_iterations}")

        # ── Buduj kontekst z poprzedniej iteracji ─────────────────────────────
        if results:
            prev_output = results[-1].output
            iter_context = feedback_template.format(
                prev_output=prev_output[:2000],
                context=context[:1000],
            )
        else:
            iter_context = current_context

        # ── Uruchom agenta ────────────────────────────────────────────────────
        result = agent(
            goal=task,
            context=iter_context,
            token_budget=token_budget_per_iteration,
            budget=budget,
            force_local=force_local,
            force_cloud=force_cloud,
            session_id=session_id,
            agent_id=f"loop-iter-{i}",
            tags=["loop"],
        )
        results.append(result)

        if result.error:
            logger.warning(f"[loop] iteracja {i+1} błąd: {result.error}")
            continue

        # ── Sprawdź warunek ukończenia ────────────────────────────────────────
        if _check_done(result.output, done_condition, checker_token_budget, budget, session_id, i):
            logger.info(f"[loop] warunek spełniony po {i+1} iteracjach")
            return LoopResult(
                results=results,
                iterations=i + 1,
                max_iterations=max_iterations,
                completed=True,
                final_output=result.output,
            )

    logger.info(f"[loop] hit max_iterations={max_iterations} bez spełnienia warunku")
    final = results[-1].output if results else ""
    return LoopResult(
        results=results,
        iterations=max_iterations,
        max_iterations=max_iterations,
        completed=False,
        final_output=final,
    )


def _check_done(
    output: str,
    condition: DoneCondition,
    checker_budget: int,
    budget: Optional[WorkflowBudget],
    session_id: str,
    iteration: int,
) -> bool:
    """Sprawdź warunek ukończenia."""
    if callable(condition):
        try:
            return bool(condition(output))
        except Exception as exc:
            logger.warning(f"[loop] done_condition callable error: {exc}")
            return False

    # Warunek opisany językiem naturalnym — mini-agent sprawdza
    check_result = agent(
        goal=(
            f"Does this output meet the following condition?\n"
            f"CONDITION: {condition}\n\n"
            f"OUTPUT:\n{output[:1500]}\n\n"
            "Answer ONLY 'YES' or 'NO'."
        ),
        token_budget=checker_budget,
        budget=budget,
        force_local=True,   # checker jest prosty — lokalny wystarczy
        session_id=session_id,
        agent_id=f"loop-checker-{iteration}",
        system=_CHECKER_SYSTEM,
        tags=["loop", "checker"],
    )
    answer = check_result.output.strip().upper()
    return answer.startswith("YES")
