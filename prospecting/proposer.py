"""
Proposal generator — tworzy draft propozycji na podstawie prompt-library/01-lead-generation.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from job_source import Job
from scorer import Score

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder-v2:16b")

_PROMPT_DIR = Path(__file__).parent.parent / "prompt-library" / "01-lead-generation"


def _load_prompt(name: str) -> str:
    p = _PROMPT_DIR / f"{name}.md"
    return p.read_text() if p.exists() else ""


def generate_proposal(job: Job, score: Score, profile: dict) -> str:
    system = _load_prompt("system")
    example = _load_prompt("example-task")

    user_prompt = f"""Write a SHORT, highly personalized Upwork proposal (max 6 sentences, no generic phrases).

FREELANCER PROFILE:
Name: {profile.get('name')}
Title: {profile.get('title')}
Skills: {', '.join(profile.get('skills', [])[:8])}

JOB:
Title: {job.title}
Budget: {job.budget}
Description: {job.description[:600]}

SCORING:
Fit: {score.fit}/10, Intent: {score.intent}/10
Reasoning: {score.reasoning}

Rules:
- Open with a specific hook tied to their problem (not "I am interested in...")
- Mention 1 relevant past experience briefly
- State clear next step (call/sample/question)
- Max 6 sentences, zero fluff
- Output ONLY the proposal text, no meta-commentary"""

    full_prompt = (f"SYSTEM: {system}\n\nEXAMPLE: {example}\n\nTASK:\n{user_prompt}"
                   if system else user_prompt)
    try:
        r = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": full_prompt, "stream": False,
                  "options": {"temperature": 0.4}},
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["response"].strip()
    except Exception as e:
        return (f"[DRY-RUN PROPOSAL — LLM error: {e}]\n\n"
                f"Hi, I specialize in {', '.join(profile.get('skills', [])[:3])} "
                f"and your project '{job.title}' is a strong match. "
                f"I've built similar pipelines and can start immediately. "
                f"Would a 15-min call work to discuss specifics?")
