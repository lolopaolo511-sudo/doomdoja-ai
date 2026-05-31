#!/usr/bin/env python3
"""
ROLA: Planner
Rozbija zadanie na konkretne kroki implementacyjne.
"""

import json
import re
from llm import call_llm

SYSTEM_PROMPT = """Jesteś planerem zadań programistycznych.
Twoim zadaniem jest rozłożenie problemu na KONKRETNE, MAŁE kroki implementacyjne.

Format odpowiedzi — zwróć TYLKO poprawny JSON:
{
  "goal": "opis celu",
  "steps": [
    {"id": 1, "title": "Krótki tytuł", "description": "Co konkretnie zrobić", "file": "nazwa_pliku.py"},
    ...
  ],
  "tests_file": "test_nazwa.py",
  "notes": "Ważne uwagi techniczne"
}

Zasady:
- Maksymalnie 5-6 kroków
- Każdy krok = jedna konkretna zmiana w kodzie
- Zawsze ostatni krok = testy
- file = plik który krok modyfikuje/tworzy
"""


def plan(task: str, context: str = "") -> dict:
    prompt = SYSTEM_PROMPT
    if context:
        prompt += f"\n\nKontekst:\n{context}"
    prompt += f"\n\nZadanie:\n{task}"

    response = call_llm(prompt, temperature=0.1)

    # Wyciągnij JSON z odpowiedzi
    match = re.search(r'\{.*\}', response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: zwróć surową odpowiedź jako prosty plan
    lines = [l.strip() for l in response.splitlines() if l.strip() and not l.startswith("{")]
    steps = [{"id": i+1, "title": l[:60], "description": l, "file": "main.py"}
             for i, l in enumerate(lines[:6])]
    return {"goal": task, "steps": steps, "tests_file": "test_main.py", "notes": response[:200]}
