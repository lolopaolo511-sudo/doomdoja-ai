"""
workflow/primitives.py — Trzy prymitywy orkiestracji dla doomdoja-ai.

    agent()    — subagent z IZOLOWANYM kontekstem i twardym budżetem tokenów
    parallel() — uruchamia N subagentów równolegle (ThreadPoolExecutor, bariera)
    pipeline() — dane płyną przez etapy sekwencyjnie

Integracja:
  - HybridRouter: wybór local/cloud per agent (jeśli model=None)
  - Memory2: zapis epizodyczny każdego wywołania
  - WorkflowBudget: twardy limit — rzuca TokenBudgetExceeded przed wysłaniem do LLM
  - Quarantine: agent czytający niezaufane dane nie wywołuje akcji

Użycie:
    from workflow import agent, parallel, pipeline, WorkflowBudget

    budget = WorkflowBudget(total=8000)
    r = agent("Podsumuj raport", context=text, token_budget=2000, budget=budget)
    print(r.output, r.tokens_used, r.backend)

    results = parallel([
        {"goal": "Zbierz oferty z RemoteOK", "context": raw_ok},
        {"goal": "Zbierz oferty z HN Hiring", "context": raw_hn},
    ], max_workers=4)

    chain = pipeline(
        stages=["Wyodrębnij fakty", "Oceń jakość", "Sformatuj raport"],
        initial_input="Treść dokumentu...",
    )
"""
from __future__ import annotations

import logging
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Union

# ── Ścieżka do korzenia repozytorium ──────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from router.router import HybridRouter, RouterContext, RouterDecision
from router.backends.cloud import CloudBackend, CloudUnavailableError
from core.llm_client import get_llm_client
from .budget import WorkflowBudget, TokenBudgetExceeded, estimate_tokens
from .quarantine import is_quarantined, quarantine as quarantine_ctx

logger = logging.getLogger("qwen_agent.workflow")

_DEFAULT_SYSTEM = (
    "Jesteś precyzyjnym asystentem. Odpowiadaj zwięźle i konkretnie. "
    "Nie powtarzaj treści kontekstu — dodaj wartość."
)
_QUARANTINE_SYSTEM = (
    "Jesteś agentem READ-ONLY. Twoim zadaniem jest TYLKO analiza i podsumowanie "
    "dostarczonych danych. NIE możesz wykonywać żadnych akcji, pisać kodu do "
    "wykonania, wydawać poleceń systemu ani instruować innych agentów do działania. "
    "Twoje wyjście jest traktowane jako niezaufane i przejdzie przez weryfikację "
    "przed jakimkolwiek użyciem."
)


# ═══════════════════════════════════════════════════════════════════════════════
# WYNIKI
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentResult:
    """Wynik pojedynczego wywołania agenta."""
    output: str
    agent_id: str
    goal: str
    model: str
    backend: str                      # "local" | "cloud"
    tokens_used: int                  # przybliżone (input + output) // 4
    elapsed_s: float
    quarantined: bool = False         # True → wyjście z trybu kwarantanny
    error: Optional[str] = None       # None = sukces
    metadata: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        status = "OK" if self.ok else f"ERR:{self.error}"
        q = " [QUARANTINE]" if self.quarantined else ""
        return (
            f"[{self.agent_id}] {status}{q} | {self.backend}/{self.model} | "
            f"~{self.tokens_used}tok | {self.elapsed_s:.1f}s"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# POMOCNICZE
# ═══════════════════════════════════════════════════════════════════════════════

_router_instance: Optional[HybridRouter] = None


def _get_router() -> HybridRouter:
    global _router_instance
    if _router_instance is None:
        _router_instance = HybridRouter()
    return _router_instance


def _call_llm(
    prompt: str,
    decision: RouterDecision,
    system: str = _DEFAULT_SYSTEM,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Wywołaj właściwy backend na podstawie decyzji routera."""
    if decision.backend == "cloud":
        backend = CloudBackend(model=decision.model)
        return backend.generate(
            prompt,
            model=decision.model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        llm = get_llm_client()
        return llm.generate(prompt, model=decision.model, temperature=temperature)


def _record_to_memory(
    agent_id: str,
    goal: str,
    result: AgentResult,
    tags: list[str],
) -> None:
    """Zapisz epizod do memory2 (nie-krytyczne — błędy logowane, nie rzucane)."""
    try:
        from memory2.memory2 import Memory2
        mem = Memory2()
        outcome = "success" if result.ok else "error"
        mem.remember(
            "episodic",
            f"workflow.agent id={agent_id} goal={goal[:80]} "
            f"model={result.model} tokens={result.tokens_used}",
            tags=["workflow", "agent"] + tags,
            meta={
                "task_id": agent_id,
                "outcome": outcome,
                "backend": result.backend,
                "model": result.model,
                "duration_s": round(result.elapsed_s, 2),
            },
        )
    except Exception as exc:
        logger.debug(f"[workflow] memory zapis pominięty: {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# PRYMITYW 1 — agent()
# ═══════════════════════════════════════════════════════════════════════════════

def agent(
    goal: str,
    context: str = "",
    *,
    model: Optional[str] = None,
    token_budget: Optional[int] = None,
    budget: Optional[WorkflowBudget] = None,
    force_local: bool = False,
    force_cloud: bool = False,
    force_quarantine: bool = False,
    session_id: str = "",
    agent_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    system: Optional[str] = None,
    temperature: float = 0.2,
    verifier_fails: int = 0,
    plan_steps_total: int = 0,
) -> AgentResult:
    """
    Uruchom subagenta z izolowanym kontekstem i opcjonalnym budżetem tokenów.

    Args:
        goal: jasny cel agenta (co ma osiągnąć)
        context: izolowany kontekst — agent widzi TYLKO to + goal
        model: konkretny model (None = router wybiera automatycznie)
        token_budget: twardy limit tokenów dla tego agenta (None = bez limitu)
        budget: WorkflowBudget do współdzielonego śledzenia (opcjonalny)
        force_local: wymuś model lokalny (np. dla danych prywatnych)
        force_cloud: wymuś cloud (np. dla złożonej syntezy)
        force_quarantine: oznacz jako kwarantannowy nawet bez context managera
        session_id: id sesji dla routera i memory
        agent_id: nadaj ID agenta (None = auto UUID)
        tags: tagi dla memory2
        system: nadpisanie system prompt (None = domyślny lub quarantine)
        temperature: temperatura LLM
        verifier_fails: liczba nieudanych rund verifier (eskalacja routera)
        plan_steps_total: liczba kroków planu (sygnał złożoności routera)

    Returns:
        AgentResult z wyjściem, użyciem tokenów i metadanymi

    Raises:
        TokenBudgetExceeded: jeśli budżet tokenów byłby przekroczony
    """
    aid = agent_id or f"a-{uuid.uuid4().hex[:8]}"
    _tags = tags or []
    in_quarantine = force_quarantine or is_quarantined()

    # ── Buduj prompt ──────────────────────────────────────────────────────────
    if context:
        prompt = f"GOAL: {goal}\n\nCONTEXT:\n{context}"
    else:
        prompt = f"GOAL: {goal}"

    # ── Szacuj tokeny i sprawdź budżet ────────────────────────────────────────
    estimated = estimate_tokens(prompt)
    if token_budget is not None:
        sub_budget = WorkflowBudget(total=token_budget, label=aid)
        sub_budget.check(estimated)
    else:
        sub_budget = None

    if budget is not None:
        budget.check(estimated)

    # ── Wybór modelu ──────────────────────────────────────────────────────────
    if model is not None:
        # Jawny model — nie pytamy routera, ale nadal rozróżniamy backend
        if any(kw in model.lower() for kw in ("claude", "anthropic", "gpt")):
            decision = RouterDecision(
                backend="cloud", model=model, provider="anthropic",
                reason=f"jawny model cloud: {model}",
            )
        else:
            decision = RouterDecision(
                backend="local", model=model, provider="ollama",
                reason=f"jawny model local: {model}",
            )
    else:
        router = _get_router()
        ctx = RouterContext(
            session_id=session_id,
            force_local=force_local or in_quarantine,
            force_cloud=force_cloud,
            verifier_fails=verifier_fails,
            plan_steps_total=plan_steps_total,
        )
        decision = router.choose_model(task=goal, context=ctx)

    # ── System prompt ─────────────────────────────────────────────────────────
    sys_prompt = system or (_QUARANTINE_SYSTEM if in_quarantine else _DEFAULT_SYSTEM)

    # ── Wywołanie LLM ─────────────────────────────────────────────────────────
    logger.info(
        f"[workflow.agent] id={aid} backend={decision.backend} "
        f"model={decision.model} quarantine={in_quarantine} est_tokens={estimated}"
    )
    start = time.monotonic()
    output = ""
    err: Optional[str] = None

    try:
        output = _call_llm(prompt, decision, system=sys_prompt, temperature=temperature)
    except TokenBudgetExceeded:
        raise
    except CloudUnavailableError as exc:
        logger.warning(f"[workflow.agent] cloud niedostępny, fallback local: {exc}")
        local_decision = RouterDecision(
            backend="local", model=_get_router().local_model,
            provider="ollama", reason=f"cloud fallback: {exc}",
        )
        try:
            output = _call_llm(prompt, local_decision, system=sys_prompt, temperature=temperature)
            decision = local_decision
        except Exception as exc2:
            err = str(exc2)
            output = ""
    except Exception as exc:
        err = str(exc)
        output = ""
        logger.error(f"[workflow.agent] {aid} błąd: {exc}")

    elapsed = time.monotonic() - start
    tokens_used = estimate_tokens(prompt) + estimate_tokens(output)

    # ── Zużycie budżetu ───────────────────────────────────────────────────────
    if sub_budget is not None:
        try:
            sub_budget.charge(tokens_used)
        except TokenBudgetExceeded:
            pass  # przekroczenie sub-budżetu tylko logujemy po fakcie
    if budget is not None:
        try:
            budget.charge(tokens_used)
        except TokenBudgetExceeded as exc:
            err = str(exc)

    result = AgentResult(
        output=output,
        agent_id=aid,
        goal=goal,
        model=decision.model,
        backend=decision.backend,
        tokens_used=tokens_used,
        elapsed_s=elapsed,
        quarantined=in_quarantine,
        error=err,
        metadata={
            "session_id": session_id,
            "decision_reason": decision.reason,
            "privacy_protected": decision.privacy_protected,
        },
    )

    _record_to_memory(aid, goal, result, _tags)

    logger.info(f"[workflow.agent] {result.summary()}")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PRYMITYW 2 — parallel()
# ═══════════════════════════════════════════════════════════════════════════════

def parallel(
    tasks: list[dict],
    max_workers: int = 4,
    timeout_s: Optional[float] = None,
    budget: Optional[WorkflowBudget] = None,
) -> list[AgentResult]:
    """
    Uruchom N subagentów równolegle. Bariera: czeka na WSZYSTKIE wyniki.

    Args:
        tasks: lista słowników — każdy to kwargs dla agent()
                np. [{"goal": "...", "context": "...", "token_budget": 1000}, ...]
        max_workers: max równoległych wątków
        timeout_s: limit czasu na WSZYSTKIE agenty łącznie (None = bez limitu)
        budget: współdzielony WorkflowBudget (opcjonalny)

    Returns:
        Lista AgentResult w tej samej kolejności co tasks (błędy = result.error != None)
    """
    if not tasks:
        return []

    results: list[Optional[AgentResult]] = [None] * len(tasks)
    current_quarantine = is_quarantined()

    def run_one(idx: int, kwargs: dict) -> tuple[int, AgentResult]:
        kw = dict(kwargs)
        if budget is not None and "budget" not in kw:
            kw["budget"] = budget
        # Propaguj stan kwarantanny do wątków potomnych
        if current_quarantine:
            kw["force_quarantine"] = True
        if current_quarantine:
            with quarantine_ctx():
                return idx, agent(**kw)
        return idx, agent(**kw)

    logger.info(f"[workflow.parallel] start {len(tasks)} agentów max_workers={max_workers}")
    start = time.monotonic()

    with ThreadPoolExecutor(max_workers=min(max_workers, len(tasks))) as pool:
        futures = {pool.submit(run_one, i, t): i for i, t in enumerate(tasks)}
        try:
            for fut in as_completed(futures, timeout=timeout_s):
                idx, res = fut.result()
                results[idx] = res
        except FuturesTimeout:
            logger.warning(f"[workflow.parallel] timeout po {timeout_s}s — niektóre agenty nie ukończyły")
            for i, r in enumerate(results):
                if r is None:
                    results[i] = AgentResult(
                        output="", agent_id=f"timeout-{i}", goal=tasks[i].get("goal", ""),
                        model="", backend="", tokens_used=0, elapsed_s=timeout_s or 0,
                        error=f"timeout po {timeout_s}s",
                    )

    elapsed = time.monotonic() - start
    ok = sum(1 for r in results if r and r.ok)
    logger.info(f"[workflow.parallel] ukończono {ok}/{len(tasks)} w {elapsed:.1f}s")

    return [r for r in results if r is not None]


# ═══════════════════════════════════════════════════════════════════════════════
# PRYMITYW 3 — pipeline()
# ═══════════════════════════════════════════════════════════════════════════════

def pipeline(
    stages: list[Union[str, dict, Callable[[str], str]]],
    initial_input: str = "",
    token_budget_per_stage: Optional[int] = None,
    budget: Optional[WorkflowBudget] = None,
    stop_on_error: bool = True,
    session_id: str = "",
) -> list[AgentResult]:
    """
    Przekazuj dane przez etapy sekwencyjnie — tańsze niż parallel gdy nie trzeba
    wszystkich wyników naraz.

    Args:
        stages: lista etapów — każdy może być:
                  str  → traktowany jako `goal` agenta; input poprzedniego etapu
                         staje się `context`
                  dict → kwargs dla agent() (goal wymagany)
                  callable(str) -> str → czysta funkcja (bez LLM)
        initial_input: dane wejściowe dla pierwszego etapu
        token_budget_per_stage: limit tokenów per etap (None = bez limitu)
        budget: WorkflowBudget dla całego pipeline'u
        stop_on_error: zatrzymaj pipeline przy błędzie etapu
        session_id: id sesji

    Returns:
        Lista AgentResult po jednym na etap (czyste funkcje zwracają wynik z error=None)
    """
    results: list[AgentResult] = []
    current_input = initial_input

    for i, stage in enumerate(stages):
        stage_id = f"pipe-{i}"
        logger.info(f"[workflow.pipeline] etap {i+1}/{len(stages)}")

        if callable(stage) and not isinstance(stage, dict):
            # Czysta funkcja — nie LLM
            start = time.monotonic()
            try:
                out = stage(current_input)
                r = AgentResult(
                    output=str(out), agent_id=stage_id,
                    goal=getattr(stage, "__name__", f"stage_{i}"),
                    model="function", backend="local",
                    tokens_used=0, elapsed_s=time.monotonic() - start,
                )
            except Exception as exc:
                r = AgentResult(
                    output="", agent_id=stage_id,
                    goal=getattr(stage, "__name__", f"stage_{i}"),
                    model="function", backend="local",
                    tokens_used=0, elapsed_s=time.monotonic() - start,
                    error=str(exc),
                )
        elif isinstance(stage, str):
            r = agent(
                goal=stage,
                context=current_input,
                token_budget=token_budget_per_stage,
                budget=budget,
                session_id=session_id,
                agent_id=stage_id,
            )
        else:
            # dict spec
            kw = dict(stage)
            kw.setdefault("context", current_input)
            if token_budget_per_stage and "token_budget" not in kw:
                kw["token_budget"] = token_budget_per_stage
            if budget and "budget" not in kw:
                kw["budget"] = budget
            kw.setdefault("session_id", session_id)
            kw["agent_id"] = stage_id
            r = agent(**kw)

        results.append(r)

        if r.error and stop_on_error:
            logger.error(f"[workflow.pipeline] etap {i} zakończony błędem — zatrzymuję")
            break

        current_input = r.output

    return results
