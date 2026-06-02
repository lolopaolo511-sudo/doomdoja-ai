"""Scorer dopasowania ogłoszeń do profilu.

fit 0-10: jak dobrze ogłoszenie pasuje do naszych kompetencji
Lokalny Ollama do oceny; fallback do heurystyki keyword-based.
Zwraca też: uzasadnienie (1-2 zdania) + sugerowany kąt oferty (1 zdanie).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from sources import Gig

_PROFILE_SUMMARY = """
Specjalizacje: web scraping, data extraction, Python automation, ETL pipelines,
AI agents (LLM), Playwright/Selenium crawlers, Airtable integration, Make.com/Zapier/n8n,
pandas, lead generation, OCR, invoice/PDF parsing, document processing, FastAPI.
Minimalna stawka: $35/h lub $300 za projekt.
"""

_SYSTEM = (
    "You are a freelance business analyst helping evaluate job fit. "
    "Respond ONLY with valid JSON — no markdown, no extra text."
)

_PROMPT = """Evaluate this job posting for a freelancer with the following profile:
{profile}

JOB POSTING:
Title: {title}
Source: {source}
Budget: {budget}
Tags: {tags}
Description (first 600 chars):
{description}

Rate fit on a scale 0-10 where:
10 = perfect match (scraping/automation/ETL/OCR/Airtable/Make.com explicitly requested)
7-9 = strong match (data, python, automation, pipelines)
4-6 = partial match (python dev but no automation/scraping mention)
0-3 = weak/irrelevant match

Also provide:
- why_fits: 1-2 sentences explaining why this is (or isn't) a match
- offer_angle: 1 sentence suggesting how to frame the proposal (or "N/A" if weak match)

Respond ONLY with JSON:
{{"fit": <0-10>, "why_fits": "<1-2 sentences>", "offer_angle": "<1 sentence>"}}"""


@dataclass
class GigScore:
    fit: int                   # 0-10
    why_fits: str
    offer_angle: str
    scored_by: str             # "llm" | "heuristic"


def score(gig: Gig, cfg: dict) -> GigScore:
    if cfg.get("use_llm", True):
        result = _llm_score(gig, cfg)
        if result:
            return result
    return _heuristic_score(gig, cfg)


def _llm_score(gig: Gig, cfg: dict) -> GigScore | None:
    url = cfg.get("ollama_url", "http://localhost:11434")
    model = cfg.get("model", "deepseek-coder-v2:16b")
    timeout = cfg.get("llm_timeout", 45)

    prompt = _PROMPT.format(
        profile=_PROFILE_SUMMARY.strip(),
        title=gig.title,
        source=gig.source,
        budget=gig.budget,
        tags=", ".join(gig.tags) if gig.tags else "—",
        description=gig.description[:600],
    )

    try:
        r = httpx.post(
            f"{url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": _SYSTEM,
                "stream": False,
                "options": {"temperature": 0.05, "num_predict": 200},
            },
            timeout=timeout,
        )
        r.raise_for_status()
        raw = r.json().get("response", "").strip()

        # Wyciągnij JSON z odpowiedzi
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        data = json.loads(raw[start:end])

        return GigScore(
            fit=max(0, min(10, int(data.get("fit", 0)))),
            why_fits=str(data.get("why_fits", "")),
            offer_angle=str(data.get("offer_angle", "")),
            scored_by="llm",
        )
    except Exception as e:
        print(f"[scorer] LLM error dla '{gig.title[:40]}': {e}")
        return None


def _heuristic_score(gig: Gig, cfg: dict) -> GigScore:
    """Keyword-based fallback bez LLM."""
    from pathlib import Path
    import yaml

    # Wczytaj profil z config.yaml jeśli przekazano ścieżkę
    strong_kw = [
        "scraping", "crawler", "data extraction", "automation", "web scraper",
        "airtable", "make.com", "zapier", "n8n", "lead gen", "lead generation",
        "invoice", "ocr", "pdf extraction", "data pipeline", "etl", "playwright",
        "selenium",
    ]
    skill_kw = [
        "python", "data", "api", "json", "csv", "spreadsheet", "google sheets",
        "automation", "workflow", "integration", "parse", "fetch", "extract",
    ]
    avoid_kw = [
        "wordpress only", "react native", "mobile app", "ios", "android",
        "shopify theme", "blockchain", "smart contract", "crypto",
    ]

    text = gig.text_blob().lower()

    if any(kw in text for kw in avoid_kw):
        return GigScore(
            fit=1,
            why_fits="Ogłoszenie zawiera technologie spoza profilu.",
            offer_angle="N/A",
            scored_by="heuristic",
        )

    strong_hits = sum(1 for kw in strong_kw if kw in text)
    skill_hits = sum(1 for kw in skill_kw if kw in text)
    fit = min(10, 1 + strong_hits * 2 + skill_hits)

    if fit >= 7:
        why = f"Silne dopasowanie — {strong_hits} kluczowych słów ({', '.join(kw for kw in strong_kw if kw in text)[:80]})."
        angle = "Zaproponuj konkretne rozwiązanie: crawler + pipeline danych z przykładem z portfolio."
    elif fit >= 4:
        why = f"Częściowe dopasowanie — {skill_hits} ogólnych słów pasujących do profilu."
        angle = "Podkreśl wcześniejsze projekty automatyzacji i możliwość szybkiego startu."
    else:
        why = "Słabe dopasowanie — brak kluczowych słów związanych ze scrapingiem lub automatyzacją."
        angle = "N/A"

    return GigScore(fit=fit, why_fits=why, offer_angle=angle, scored_by="heuristic")
