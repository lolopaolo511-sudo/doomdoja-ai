"""
Scorer — ocenia dopasowanie ogłoszenia do profilu (fit 1-10, intent 1-10).
Używa lokalnego LLM przez Ollama; fallback do heurystyki keyword-based.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from job_source import Job

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder-v2:16b")


@dataclass
class Score:
    fit: int        # 1-10: jak dobrze ogłoszenie pasuje do profilu
    intent: int     # 1-10: jak poważny/zdeterminowany jest klient
    reasoning: str
    should_apply: bool


def _keyword_score(job: Job, profile: dict) -> Score:
    """Heurystyczny fallback bez LLM."""
    text = (job.title + " " + job.description).lower()
    avoid = profile.get("avoid_keywords", [])
    strong = profile.get("strong_match_keywords", [])
    skills = profile.get("skills", [])

    if any(kw.lower() in text for kw in avoid):
        return Score(fit=1, intent=5, reasoning="Ogłoszenie zawiera słowa do unikania.", should_apply=False)

    fit_hits = sum(1 for kw in strong if kw.lower() in text)
    skill_hits = sum(1 for s in skills if s.lower() in text)
    fit = min(10, 2 + fit_hits * 2 + skill_hits)

    intent = 5
    if any(w in text for w in ["long term", "ongoing", "reliable", "quality"]):
        intent += 2
    if any(w in text for w in ["urgent", "asap", "immediately"]):
        intent += 1
    if "$" in job.budget and any(c.isdigit() for c in job.budget):
        nums = re.findall(r"\d+", job.budget.replace(",", ""))
        if nums and int(nums[-1]) >= 500:
            intent += 1
    intent = min(10, intent)

    return Score(
        fit=fit,
        intent=intent,
        reasoning=f"Keyword match: {fit_hits} strong, {skill_hits} skills.",
        should_apply=fit >= 6 and intent >= 5,
    )


def _llm_score(job: Job, profile: dict) -> Score:
    prompt = f"""You are an expert freelancer evaluating an Upwork job posting.

PROFILE:
Title: {profile.get('title')}
Skills: {', '.join(profile.get('skills', []))}
Rate: ${profile.get('hourly_rate_min')}-{profile.get('hourly_rate_max')}/h
Avoid: {', '.join(profile.get('avoid_keywords', []))}

JOB:
Title: {job.title}
Budget: {job.budget}
Description: {job.description[:800]}

Rate this job on two dimensions (1-10 integer):
- fit: how well the job matches the profile skills
- intent: how serious/ready-to-hire the client is (big budget, clear scope = high)

Respond ONLY with valid JSON, no markdown:
{{"fit": <1-10>, "intent": <1-10>, "reasoning": "<one sentence>", "should_apply": <true|false>}}"""

    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1}},
            timeout=60,
        )
        r.raise_for_status()
        raw = r.json()["response"].strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        return Score(
            fit=int(data.get("fit", 5)),
            intent=int(data.get("intent", 5)),
            reasoning=data.get("reasoning", ""),
            should_apply=bool(data.get("should_apply", False)),
        )
    except Exception as e:
        print(f"[scorer] LLM error ({e}), fallback do heurystyki")
        return _keyword_score(job, profile)


def score_job(job: Job, profile: dict, use_llm: bool = True) -> Score:
    if use_llm:
        return _llm_score(job, profile)
    return _keyword_score(job, profile)
