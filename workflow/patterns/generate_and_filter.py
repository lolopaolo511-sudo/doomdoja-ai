"""
workflow/patterns/generate_and_filter.py

Wzorzec: GENERUJ → FILTRUJ

Generuj 5-30 opcji (brainstorm), a następnie odfiltruj przez rubryczkę + dedup.
Lepsze niż prosić jeden model o „najlepszą odpowiedź" — szerszy coverage.

Użycie:
    from workflow.patterns import generate_and_filter

    result = generate_and_filter(
        prompt="Tytuły projektów AI dla freelancera",
        rubric="Zachowaj tylko tytuły wskazujące na konkretną specjalizację "
               "(scraping / ETL / automation). Odrzuć ogólniki.",
        n=15,
        top_k=5,
    )
    for item in result.kept:
        print(f"[{item['score']}] {item['text']}")
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from ..primitives import agent
from ..budget import WorkflowBudget

logger = logging.getLogger("qwen_agent.workflow.gen_filter")


@dataclass
class FilteredResult:
    kept: list[dict]          # [{"text": str, "score": int, "index": int}]
    all_generated: list[str]
    generator_tokens: int
    filter_tokens: int
    total_tokens: int
    dedup_removed: int
    parse_error: bool = False


_GENERATOR_SYSTEM = (
    "You are a creative brainstorming assistant. "
    "Generate diverse, concrete options. No fluff. No numbering explanation — "
    "just the numbered list."
)

_FILTER_SYSTEM = (
    "You are a strict quality filter. Apply the rubric ruthlessly. "
    "Return ONLY valid JSON — no markdown, no commentary."
)

_FILTER_PROMPT = """\
Filter and rank these {n} options according to the rubric.
Keep only the top {top_k}. Reject everything that doesn't clearly pass.

RUBRIC:
{rubric}

OPTIONS:
{options_text}

Return ONLY this JSON:
{{
  "kept": [
    {{"index": <1-based>, "text": "<exact text>", "score": <0-10>}},
    ...
  ]
}}
"""


def generate_and_filter(
    prompt: str,
    rubric: str,
    *,
    n: int = 10,
    top_k: int = 3,
    context: str = "",
    generator_token_budget: int = 2000,
    filter_token_budget: int = 1500,
    budget: Optional[WorkflowBudget] = None,
    generator_force_cloud: bool = False,
    filter_force_cloud: bool = False,
    session_id: str = "",
) -> FilteredResult:
    """
    Generuj N opcji, odfiltruj przez rubryczkę, zwróć top-K.

    Args:
        prompt: co generować (tytuły, pomysły, strategie, etc.)
        rubric: kryteria filtrowania — co zachować, co odrzucić
        n: ile opcji wygenerować (5-30)
        top_k: ile zachować po filtrowaniu
        context: dodatkowy kontekst dla generatora
        generator_token_budget: limit tokenów generatora
        filter_token_budget: limit tokenów filtra
        budget: WorkflowBudget (opcjonalny)
        generator_force_cloud: wymuś cloud dla generatora
        filter_force_cloud: wymuś cloud dla filtra
        session_id: id sesji

    Returns:
        FilteredResult z listą zachowanych opcji i metadanymi
    """
    # ── Krok 1: generacja ─────────────────────────────────────────────────────
    gen_goal = (
        f"Generate exactly {n} options for: {prompt}\n"
        f"Format: numbered list (1. ... 2. ... etc.)\n"
        f"Be specific and diverse. No duplicates."
    )

    gen_result = agent(
        goal=gen_goal,
        context=context,
        token_budget=generator_token_budget,
        budget=budget,
        force_cloud=generator_force_cloud,
        session_id=session_id,
        agent_id="generator",
        system=_GENERATOR_SYSTEM,
        tags=["generate"],
    )

    raw_options = _parse_numbered_list(gen_result.output)
    logger.info(f"[gen_filter] wygenerowano {len(raw_options)} opcji")

    # ── Krok 2: dedup ─────────────────────────────────────────────────────────
    before_dedup = len(raw_options)
    raw_options = _dedup(raw_options)
    dedup_removed = before_dedup - len(raw_options)
    if dedup_removed:
        logger.info(f"[gen_filter] dedup usunął {dedup_removed} duplikatów")

    if not raw_options:
        return FilteredResult(
            kept=[], all_generated=[], generator_tokens=gen_result.tokens_used,
            filter_tokens=0, total_tokens=gen_result.tokens_used,
            dedup_removed=dedup_removed, parse_error=True,
        )

    # ── Krok 3: filtrowanie ───────────────────────────────────────────────────
    options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(raw_options))
    filter_goal = _FILTER_PROMPT.format(
        n=len(raw_options),
        top_k=min(top_k, len(raw_options)),
        rubric=rubric.strip(),
        options_text=options_text,
    )

    filter_result = agent(
        goal=filter_goal,
        token_budget=filter_token_budget,
        budget=budget,
        force_cloud=filter_force_cloud,
        session_id=session_id,
        agent_id="filter",
        system=_FILTER_SYSTEM,
        tags=["filter"],
    )

    kept, parse_error = _parse_filter_output(filter_result.output, raw_options, top_k)

    total = gen_result.tokens_used + filter_result.tokens_used
    return FilteredResult(
        kept=kept,
        all_generated=raw_options,
        generator_tokens=gen_result.tokens_used,
        filter_tokens=filter_result.tokens_used,
        total_tokens=total,
        dedup_removed=dedup_removed,
        parse_error=parse_error,
    )


def _parse_numbered_list(text: str) -> list[str]:
    """Parsuj numerowaną listę: '1. ...' lub '1) ...'"""
    lines = text.strip().split("\n")
    results = []
    for line in lines:
        line = line.strip()
        m = re.match(r"^\d+[\.\)]\s+(.+)", line)
        if m:
            results.append(m.group(1).strip())
        elif line and not re.match(r"^\d+$", line):
            # Linia bez numeru ale nie pusta — może to bullet
            if line.startswith(("-", "•", "*")):
                results.append(line.lstrip("-•* ").strip())
    return [r for r in results if r]


def _dedup(options: list[str], threshold: float = 0.8) -> list[str]:
    """Prosta deduplicacja: usuń opcje które zaczynają się tak samo (>80% overlap)."""
    seen: list[str] = []
    for opt in options:
        opt_lower = opt.lower().strip()
        is_dup = False
        for s in seen:
            s_lower = s.lower().strip()
            # Overlap = wspólne słowa / słowa w krótszym
            words_a = set(opt_lower.split())
            words_b = set(s_lower.split())
            if not words_a or not words_b:
                continue
            overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
            if overlap >= threshold:
                is_dup = True
                break
        if not is_dup:
            seen.append(opt)
    return seen


def _parse_filter_output(
    text: str, options: list[str], top_k: int
) -> tuple[list[dict], bool]:
    """Parsuj JSON z wynikami filtrowania."""
    try:
        text_clean = re.sub(r"```(?:json)?\s*", "", text)
        text_clean = text_clean.replace("```", "").strip()
        match = re.search(r"\{.*\}", text_clean, re.DOTALL)
        data = json.loads(match.group() if match else text_clean)
        kept = data.get("kept", [])
        # Uzupełnij brakujące pola
        result = []
        for item in kept[:top_k]:
            result.append({
                "index": int(item.get("index", 0)),
                "text": str(item.get("text", "")),
                "score": int(item.get("score", 5)),
            })
        return result, False
    except Exception as exc:
        logger.warning(f"[gen_filter] parse filter error: {exc}")
        # Fallback: zwróć pierwsze top_k bez scorów
        fallback = [{"index": i+1, "text": opt, "score": 5}
                    for i, opt in enumerate(options[:top_k])]
        return fallback, True
