"""
workflow/patterns/tournament.py

Wzorzec: TURNIEJ (pairwise comparison → ranking)

Dla N kandydatów wykonuje N*(N-1)/2 porównań parami.
Najlepsze do rankingu rzeczy subiektywnych (szablony, opisy, nazwy).

Uwaga: O(N²) wywołań LLM — używaj dla N <= 8.
Dla większych N użyj generate_and_filter zamiast tego.

Użycie:
    from workflow.patterns import tournament

    result = tournament(
        candidates=[
            "Tytuł A: Python Scraping Expert",
            "Tytuł B: Data Extraction Specialist",
            "Tytuł C: Automation & ETL Developer",
        ],
        criterion="Który tytuł lepiej przyciąga klientów szukających scrapingu?",
    )
    print(result.ranking)    # [(kandydat, wynik), ...] posortowane
    print(result.winner)     # najlepszy
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from ..primitives import agent, parallel
from ..budget import WorkflowBudget

logger = logging.getLogger("qwen_agent.workflow.tournament")


@dataclass
class TournamentResult:
    ranking: list[tuple[str, int]]    # [(kandydat, punkty), ...] od najlepszego
    match_count: int
    total_tokens: int
    parse_errors: int

    @property
    def winner(self) -> str:
        return self.ranking[0][0] if self.ranking else ""

    def report(self) -> str:
        lines = ["=== Turniej ==="]
        for i, (cand, pts) in enumerate(self.ranking, 1):
            lines.append(f"  {i}. [{pts} pkt] {cand[:80]}")
        lines.append(f"  Mecze: {self.match_count} | "
                     f"Tokeny: {self.total_tokens} | Błędy: {self.parse_errors}")
        return "\n".join(lines)


_MATCH_SYSTEM = (
    "You are an objective judge. Compare two options based on the criterion. "
    "Return ONLY valid JSON."
)

_MATCH_PROMPT = """\
Compare these two options based on the criterion:

CRITERION: {criterion}

Option A:
{a}

Option B:
{b}

Which is better for the criterion?
Return ONLY this JSON:
{{"winner": "A" | "B" | "TIE", "reason": "<1 sentence>"}}
"""


def tournament(
    candidates: list[str],
    criterion: str,
    *,
    token_budget_per_match: int = 400,
    budget: Optional[WorkflowBudget] = None,
    max_workers: int = 4,
    force_cloud: bool = False,
    session_id: str = "",
) -> TournamentResult:
    """
    Przeprowadź turniej pairwise comparison dla listy kandydatów.

    Args:
        candidates: lista opcji do porównania (max 8 dla sensownego kosztu)
        criterion: kryterium oceny (co sprawdzamy)
        token_budget_per_match: limit tokenów per mecz
        budget: WorkflowBudget (opcjonalny)
        max_workers: max równoległych meczów
        force_cloud: wymuś cloud dla sędziego
        session_id: id sesji

    Returns:
        TournamentResult z rankingiem
    """
    if len(candidates) < 2:
        raise ValueError("Turniej wymaga co najmniej 2 kandydatów")
    if len(candidates) > 8:
        logger.warning(
            f"[tournament] {len(candidates)} kandydatów → "
            f"{len(candidates)*(len(candidates)-1)//2} meczów — może być kosztowne"
        )

    scores = {c: 0 for c in candidates}
    pairs = [
        (i, j, a, b)
        for i, a in enumerate(candidates)
        for j, b in enumerate(candidates)
        if i < j
    ]

    # ── Przygotuj mecze jako parallel tasks ───────────────────────────────────
    tasks = []
    for i, j, a, b in pairs:
        tasks.append({
            "goal": _MATCH_PROMPT.format(criterion=criterion, a=a, b=b),
            "token_budget": token_budget_per_match,
            "force_cloud": force_cloud,
            "session_id": session_id,
            "agent_id": f"match-{i}v{j}",
            "system": _MATCH_SYSTEM,
            "tags": ["tournament", "match"],
        })
    if budget:
        for t in tasks:
            t["budget"] = budget

    logger.info(f"[tournament] {len(candidates)} kandydatów → {len(pairs)} meczów")
    match_results = parallel(tasks, max_workers=max_workers)

    # ── Oblicz wyniki ─────────────────────────────────────────────────────────
    total_tokens = 0
    parse_errors = 0

    for (i, j, a, b), result in zip(pairs, match_results):
        total_tokens += result.tokens_used
        try:
            winner_label = _parse_match(result.output)
            if winner_label == "A":
                scores[a] += 1
            elif winner_label == "B":
                scores[b] += 1
            else:  # TIE
                scores[a] += 0
                scores[b] += 0
        except Exception as exc:
            logger.warning(f"[tournament] parse error mecz {i}v{j}: {exc}")
            parse_errors += 1

    ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return TournamentResult(
        ranking=ranking,
        match_count=len(pairs),
        total_tokens=total_tokens,
        parse_errors=parse_errors,
    )


def _parse_match(text: str) -> str:
    """Wyodrębnij zwycięzcę ('A', 'B' lub 'TIE') z JSON odpowiedzi."""
    text_clean = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    try:
        match = re.search(r"\{.*\}", text_clean, re.DOTALL)
        data = json.loads(match.group() if match else text_clean)
        winner = str(data.get("winner", "TIE")).strip().upper()
        if winner in ("A", "B", "TIE"):
            return winner
    except Exception:
        pass
    # Fallback: szukaj słów A/B w tekście
    upper = text.upper()
    if re.search(r"\bWINNER[:\s]+A\b", upper) or re.search(r"\bOPTION A\b", upper[:50]):
        return "A"
    if re.search(r"\bWINNER[:\s]+B\b", upper) or re.search(r"\bOPTION B\b", upper[:50]):
        return "B"
    return "TIE"
