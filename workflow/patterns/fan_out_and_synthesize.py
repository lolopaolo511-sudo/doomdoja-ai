"""
workflow/patterns/fan_out_and_synthesize.py

Wzorzec: ROZGAŁĘŹ → ZBIERZ RÓWNOLEGLE → SYNTETYZUJ

Idealne gdy masz N niezależnych źródeł/podzadań, które można przetworzyć
równolegle, a następnie jeden agent łączy wszystkie wyniki.

Kluczowa właściwość izolacji:
  - Każdy agent widzi TYLKO swoje dane (zero cross-contamination)
  - Synteza dostaje tylko WYNIKI agentów (nie surowe dane wejściowe)

Użycie:
    from workflow.patterns import fan_out_and_synthesize

    subtasks = [
        {"goal": "Wyodrębnij ogłoszenia scraperów",   "context": raw_remoteok},
        {"goal": "Wyodrębnij ogłoszenia data science", "context": raw_hn},
        {"goal": "Wyodrębnij ogłoszenia Python dev",  "context": raw_upwork},
    ]
    result = fan_out_and_synthesize(
        subtasks=subtasks,
        synthesize_goal="Wybierz TOP 5 ogłoszeń i oceń dopasowanie do profilu",
        force_quarantine_subtasks=True,   # dane z sieci → kwarantanna
    )
    print(result.synthesis.output)
    print(result.report())
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..primitives import agent, parallel, AgentResult
from ..budget import WorkflowBudget
from ..quarantine import quarantine

logger = logging.getLogger("qwen_agent.workflow.fan_out")


@dataclass
class FanOutResult:
    subtask_results: list[AgentResult]
    synthesis: AgentResult
    total_tokens: int
    ok_count: int
    failed_count: int

    def report(self) -> str:
        lines = ["=== FanOut+Synthesize ==="]
        for i, r in enumerate(self.subtask_results):
            status = "OK" if r.ok else f"BŁĄD: {r.error}"
            lines.append(f"  [{i+1}] {r.goal[:60]} → {status} ({r.tokens_used}tok)")
        lines.append(f"  [SYNTEZA] {self.synthesis.goal[:60]} → "
                     f"{'OK' if self.synthesis.ok else 'BŁĄD'} ({self.synthesis.tokens_used}tok)")
        lines.append(f"  Łącznie: {self.total_tokens} tokenów | "
                     f"{self.ok_count} OK / {self.failed_count} błędów")
        return "\n".join(lines)


def fan_out_and_synthesize(
    subtasks: list[dict],
    *,
    synthesize_goal: str = "Syntetyzuj wyniki wszystkich agentów w spójną odpowiedź.",
    synthesize_context: str = "",
    max_workers: int = 6,
    subtask_token_budget: int = 1500,
    synthesizer_token_budget: int = 3000,
    budget: Optional[WorkflowBudget] = None,
    force_quarantine_subtasks: bool = False,
    synthesizer_force_cloud: bool = False,
    session_id: str = "",
    timeout_s: Optional[float] = None,
) -> FanOutResult:
    """
    Uruchom N subtask agentów równolegle, następnie jeden agent syntetyzuje.

    Args:
        subtasks: lista słowników — kwargs dla agent(); wymagane pole "goal"
        synthesize_goal: co synteza ma zrobić z zebranymi wynikami
        synthesize_context: dodatkowy kontekst dla syntezatora
        max_workers: max równoległych wątków dla subtask agentów
        subtask_token_budget: limit tokenów per subtask agent
        synthesizer_token_budget: limit tokenów dla syntezatora
        budget: WorkflowBudget dla całości
        force_quarantine_subtasks: uruchom subtask agenty w kwarantannie
                                    (dla danych z niezaufanych źródeł)
        synthesizer_force_cloud: wymuś cloud dla syntezatora (złożona operacja)
        session_id: id sesji
        timeout_s: timeout dla fazy fan-out

    Returns:
        FanOutResult z listą wyników i syntezą
    """
    # ── Przygotuj task specyfikacje ───────────────────────────────────────────
    prepared = []
    for i, spec in enumerate(subtasks):
        kw = dict(spec)
        kw.setdefault("token_budget", subtask_token_budget)
        kw.setdefault("session_id", session_id)
        kw.setdefault("agent_id", f"fanout-{i}")
        if budget:
            kw["budget"] = budget
        prepared.append(kw)

    # ── Fan-out: równoległe wykonanie ─────────────────────────────────────────
    logger.info(f"[fan_out] start {len(prepared)} subtask agentów "
                f"quarantine={force_quarantine_subtasks}")

    if force_quarantine_subtasks:
        with quarantine():
            sub_results = parallel(prepared, max_workers=max_workers, timeout_s=timeout_s)
    else:
        sub_results = parallel(prepared, max_workers=max_workers,
                               budget=budget, timeout_s=timeout_s)

    # ── Zbierz wyniki (tylko OK) ──────────────────────────────────────────────
    ok_results = [r for r in sub_results if r.ok and r.output.strip()]
    failed = [r for r in sub_results if not r.ok]

    logger.info(f"[fan_out] zebrano {len(ok_results)}/{len(sub_results)} OK")

    # ── Synteza: JEDEN agent, widzi TYLKO wyniki (nie surowe dane) ────────────
    combined_outputs = "\n\n".join(
        f"--- Wynik agenta {i+1} (goal: {r.goal[:60]}) ---\n{r.output}"
        for i, r in enumerate(ok_results)
    )

    synth_context = combined_outputs
    if synthesize_context:
        synth_context = f"{synthesize_context}\n\n{combined_outputs}"

    synthesis = agent(
        goal=synthesize_goal,
        context=synth_context,
        token_budget=synthesizer_token_budget,
        budget=budget,
        force_cloud=synthesizer_force_cloud,
        session_id=session_id,
        agent_id="synthesizer",
    )

    total_tokens = sum(r.tokens_used for r in sub_results) + synthesis.tokens_used

    return FanOutResult(
        subtask_results=sub_results,
        synthesis=synthesis,
        total_tokens=total_tokens,
        ok_count=len(ok_results),
        failed_count=len(failed),
    )
