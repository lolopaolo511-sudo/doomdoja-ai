"""
workflow/patterns/adversarial_verification.py

Wzorzec: WERYFIKACJA WROGIA

Osobny agent WERYFIKATOR nie ma dostępu do:
  - tożsamości autora/generatora
  - oryginalnego promptu generującego
  - kontekstu decyzji (scorera, rankerów)

Ocenia treść wyłącznie na podstawie RUBRYKI i ZAWARTOŚCI.
Rozwiązuje problem „zbyt łaskawego scorera" — weryfikator nie ma incentywy
by być pobłażliwym.

Zwraca: werdykt (PASS/FAIL/UNCERTAIN), wynik 0-10, lista problemów.

Użycie:
    from workflow.patterns import adversarial_verification, Verdict

    result = adversarial_verification(
        content="Senior Python dev needed for scraping project. $50/h...",
        rubric=(
            "ODRZUĆ jeśli: brak budżetu, stare ogłoszenie (>30 dni), "
            "wymaga pracy biurowej, nie-remote. "
            "PRZEPUŚĆ jeśli: scraping/automation/ETL, remote, $35+/h."
        ),
    )
    if result.verdict == Verdict.PASS:
        print("Ogłoszenie zaakceptowane:", result.score)
    else:
        print("Odrzucone:", result.reasons)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..primitives import agent, AgentResult
from ..budget import WorkflowBudget

logger = logging.getLogger("qwen_agent.workflow.adversarial")


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class AdversarialResult:
    verdict: Verdict
    score: int               # 0-10
    reasons: list[str]
    raw_output: str
    verifier_model: str
    verifier_backend: str
    tokens_used: int
    parse_error: bool = False

    @property
    def passed(self) -> bool:
        return self.verdict == Verdict.PASS


_VERIFIER_SYSTEM = (
    "You are an adversarial quality checker. Your job is to find flaws, "
    "inconsistencies, outdated information, and mismatches. "
    "You do NOT know who created the content or why — judge ONLY the content "
    "against the rubric. Be strict. Return ONLY valid JSON."
)

_VERIFIER_PROMPT = """\
Critically evaluate the following CONTENT against the RUBRIC.
Find every reason to reject it. Do not be lenient.

RUBRIC:
{rubric}

CONTENT:
{content}

Return ONLY this JSON (no markdown, no extra text):
{{
  "verdict": "PASS" | "FAIL" | "UNCERTAIN",
  "score": <integer 0-10>,
  "reasons": ["<issue 1>", "<issue 2>", ...]
}}

Scoring guide:
  8-10: clearly passes rubric — no real issues
  5-7:  minor issues — passes with caveats
  2-4:  significant issues — marginal
  0-1:  clearly fails rubric
"""


def adversarial_verification(
    content: str,
    rubric: str,
    *,
    pass_threshold: int = 5,
    verifier_model: Optional[str] = None,
    token_budget: int = 1500,
    budget: Optional[WorkflowBudget] = None,
    force_cloud: bool = False,
    session_id: str = "",
    verifier_id: Optional[str] = None,
) -> AdversarialResult:
    """
    Uruchom adversarial weryfikację treści.

    Kluczowa izolacja: weryfikator NIE widzi:
      - oryginalnego promptu który wygenerował content
      - historii poprzednich ocen
      - tożsamości autora

    Args:
        content: treść do weryfikacji (ogłoszenie, raport, kod, etc.)
        rubric: kryteria oceny — co przepuszczać, co odrzucać
        pass_threshold: minimalny score dla PASS (domyślnie 5)
        verifier_model: konkretny model (None = router wybiera)
        token_budget: limit tokenów dla weryfikatora
        budget: WorkflowBudget (opcjonalny)
        force_cloud: wymuś cloud (lepsze dla złożonej weryfikacji)
        session_id: id sesji
        verifier_id: nadaj ID weryfikatora (None = auto)

    Returns:
        AdversarialResult z werdyktem, wynikiem i listą problemów
    """
    prompt = _VERIFIER_PROMPT.format(
        rubric=rubric.strip(),
        content=content[:3000],  # ogranicz długość contentu
    )

    result = agent(
        goal=prompt,
        model=verifier_model,
        token_budget=token_budget,
        budget=budget,
        force_cloud=force_cloud,
        session_id=session_id,
        agent_id=verifier_id or "adversarial-verifier",
        system=_VERIFIER_SYSTEM,
        tags=["adversarial", "verifier"],
    )

    return _parse_verifier_output(result, pass_threshold)


def adversarial_verification_batch(
    items: list[str],
    rubric: str,
    *,
    pass_threshold: int = 5,
    max_workers: int = 4,
    token_budget_per_item: int = 1000,
    budget: Optional[WorkflowBudget] = None,
    force_cloud: bool = False,
    session_id: str = "",
) -> list[AdversarialResult]:
    """
    Zweryfikuj wiele elementów równolegle (np. listę ogłoszeń).
    Używa parallel() wewnętrznie.
    """
    from ..primitives import parallel

    prompt_template = _VERIFIER_PROMPT

    tasks = [
        {
            "goal": prompt_template.format(rubric=rubric.strip(), content=item[:3000]),
            "model": None,
            "token_budget": token_budget_per_item,
            "force_cloud": force_cloud,
            "session_id": session_id,
            "agent_id": f"adv-{i}",
            "system": _VERIFIER_SYSTEM,
            "tags": ["adversarial", "verifier"],
        }
        for i, item in enumerate(items)
    ]

    if budget:
        for t in tasks:
            t["budget"] = budget

    raw_results = parallel(tasks, max_workers=max_workers)
    return [_parse_verifier_output(r, pass_threshold) for r in raw_results]


def _parse_verifier_output(result: AgentResult, pass_threshold: int) -> AdversarialResult:
    """Parsuj JSON z wyjścia weryfikatora."""
    raw = result.output
    parse_error = False

    try:
        data = _extract_json(raw)
        raw_verdict = str(data.get("verdict", "UNCERTAIN")).upper().strip()
        score = int(data.get("score", 5))
        reasons = data.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = [str(reasons)]

        # Mapuj verdykt na enum, uwzględniając threshold
        if raw_verdict == "PASS" and score >= pass_threshold:
            verdict = Verdict.PASS
        elif raw_verdict == "FAIL" or score < pass_threshold:
            verdict = Verdict.FAIL
        else:
            verdict = Verdict.UNCERTAIN

    except Exception as exc:
        logger.warning(f"[adversarial] parse error: {exc} | raw={raw[:200]}")
        parse_error = True
        # Fallback: szukaj słów PASS/FAIL w tekście
        upper = raw.upper()
        if "PASS" in upper and "FAIL" not in upper:
            verdict, score, reasons = Verdict.PASS, 6, []
        else:
            verdict, score, reasons = Verdict.FAIL, 2, [f"parse error: {exc}"]

    return AdversarialResult(
        verdict=verdict,
        score=score,
        reasons=reasons,
        raw_output=raw,
        verifier_model=result.model,
        verifier_backend=result.backend,
        tokens_used=result.tokens_used,
        parse_error=parse_error,
    )


def _extract_json(text: str) -> dict:
    """Wyodrębnij JSON z tekstu (obsługuje markdown code blocks)."""
    # Usuń markdown
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "").strip()
    # Znajdź { ... }
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)
