"""
workflow/patterns/classify_and_act.py

Wzorzec: KLASYFIKUJ → DZIAŁAJ

Klasyfikator (lekki, fast model) rozpoznaje typ zadania, a następnie kieruje
do odpowiedniego handlera (agent spec lub callable). Klucz "default" obsługuje
nierozpoznane kategorie.

Użycie:
    from workflow.patterns import classify_and_act

    result = classify_and_act(
        task="Napisz scraper dla ogłoszeń Upwork",
        categories={
            "scraping":    {"goal": "Zaprojektuj architekturę scrapera: {task}",
                            "force_local": True},
            "etl":         {"goal": "Zaprojektuj pipeline ETL: {task}"},
            "automation":  {"goal": "Zaplanuj automatyzację: {task}",
                            "force_cloud": True},
            "default":     {"goal": "Wykonaj ogólne zadanie: {task}"},
        },
    )
    print(result.category, result.output)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Callable, Optional, Union

from ..primitives import agent, AgentResult
from ..budget import WorkflowBudget

logger = logging.getLogger("qwen_agent.workflow.classify_and_act")

HandlerSpec = Union[dict, Callable[[str, str], AgentResult]]


@dataclass
class ClassifyResult:
    category: str
    output: str
    agent_id: str
    model: str
    backend: str
    tokens_used: int
    classifier_tokens: int
    raw_classification: str


def classify_and_act(
    task: str,
    categories: dict[str, HandlerSpec],
    *,
    context: str = "",
    classifier_model: Optional[str] = None,
    classifier_budget: int = 300,
    handler_budget: Optional[int] = None,
    budget: Optional[WorkflowBudget] = None,
    session_id: str = "",
) -> ClassifyResult:
    """
    Klasyfikuj zadanie, następnie przekieruj do właściwego handlera.

    Args:
        task: treść zadania do sklasyfikowania i wykonania
        categories: słownik nazwa→handler; handler to:
                    - dict kwargs dla agent() (placeholder {task} i {context} zastępowany)
                    - callable(task, context) -> AgentResult
                    Klucz "default" wymagany jako fallback.
        context: dodatkowy kontekst (opcjonalny)
        classifier_model: model klasyfikatora (None = fast model przez router)
        classifier_budget: budżet tokenów dla klasyfikatora
        handler_budget: budżet tokenów dla handlera (None = bez limitu)
        budget: WorkflowBudget dla całości
        session_id: id sesji

    Returns:
        ClassifyResult z kategorią i wynikiem handlera
    """
    if "default" not in categories:
        categories = dict(categories)
        categories["default"] = {"goal": "Wykonaj zadanie: {task}"}

    category_names = [k for k in categories if k != "default"]

    # ── Krok 1: klasyfikacja ──────────────────────────────────────────────────
    classify_prompt = (
        f"Classify this task into EXACTLY ONE of these categories: "
        f"{', '.join(category_names)}\n\n"
        f"Task: {task}\n\n"
        "Return ONLY the category name, nothing else. "
        f"If unsure, return: default"
    )

    cls_result = agent(
        goal=classify_prompt,
        context=context[:500] if context else "",
        model=classifier_model,
        token_budget=classifier_budget,
        budget=budget,
        session_id=session_id,
        agent_id="classify",
        force_local=True,  # klasyfikacja zawsze lokalnie — szybka i tania
    )

    raw = cls_result.output.strip().lower()
    # Wyodrębnij czystą nazwę kategorii
    category = _extract_category(raw, list(categories.keys()))
    logger.info(f"[classify_and_act] raw='{raw[:80]}' → kategoria='{category}'")

    # ── Krok 2: handler ───────────────────────────────────────────────────────
    handler = categories.get(category) or categories["default"]
    if category not in categories:
        category = "default"

    if callable(handler):
        act_result = handler(task, context)
    else:
        kw = dict(handler)
        # Interpolacja placeholderów
        if "goal" in kw:
            kw["goal"] = kw["goal"].replace("{task}", task).replace("{context}", context)
        kw.setdefault("context", context)
        if handler_budget and "token_budget" not in kw:
            kw["token_budget"] = handler_budget
        if budget:
            kw.setdefault("budget", budget)
        kw.setdefault("session_id", session_id)
        act_result = agent(**kw)

    return ClassifyResult(
        category=category,
        output=act_result.output,
        agent_id=act_result.agent_id,
        model=act_result.model,
        backend=act_result.backend,
        tokens_used=act_result.tokens_used + cls_result.tokens_used,
        classifier_tokens=cls_result.tokens_used,
        raw_classification=raw,
    )


def _extract_category(raw: str, valid: list[str]) -> str:
    """Wyodrębnij kategorię z odpowiedzi klasyfikatora."""
    raw_stripped = raw.strip().strip('"\'').lower()
    # Dokładne dopasowanie
    for cat in valid:
        if cat.lower() == raw_stripped:
            return cat
    # Częściowe dopasowanie (kategoria jako podciąg odpowiedzi)
    for cat in valid:
        if cat.lower() in raw_stripped:
            return cat
    return "default"
