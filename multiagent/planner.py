#!/usr/bin/env python3
"""
ROLA: Planner (v2 — z acceptance criteria, checkpointami i persystencją stanu)

Nowe funkcje vs v1:
  - Każdy krok ma jawne acceptance_criteria (lista warunków do sprawdzenia)
  - Pola checkpoint i depends_on dla długich zadań
  - save_state / load_state — wznawianie przerwanych zadań (plan_state.json)
  - plan_resumed() — kontynuuje od ostatniego nieukończonego kroku

Kompatybilność wsteczna:
  - plan(task) nadal działa identycznie jak w v1
  - Dodatkowe pola w JSON są ignorowane przez starszy kod
"""

import json
import re
from pathlib import Path
from llm import call_llm

SYSTEM_PROMPT = """Jesteś planerem zadań programistycznych (v2).
Twoim zadaniem jest rozłożenie problemu na KONKRETNE, MAŁE kroki implementacyjne
z jawnymi kryteriami ukończenia.

Format odpowiedzi — zwróć TYLKO poprawny JSON:
{
  "goal": "opis celu",
  "steps": [
    {
      "id": 1,
      "title": "Krótki tytuł",
      "description": "Co konkretnie zrobić",
      "file": "nazwa_pliku.py",
      "acceptance_criteria": [
        "Plik istnieje i nie jest pusty",
        "Funkcja X przyjmuje argumenty Y i Z",
        "Brak błędów składni"
      ],
      "checkpoint": "step_1_done",
      "depends_on": []
    }
  ],
  "tests_file": "test_nazwa.py",
  "notes": "Ważne uwagi techniczne",
  "verification_type": "python|html|javascript|generic"
}

Zasady:
- Maksymalnie 5-6 kroków
- Każdy krok = jedna konkretna zmiana w kodzie
- acceptance_criteria: 2-4 konkretne, sprawdzalne warunki (nie ogólniki)
- verification_type: jaki typ pliku jest głównym artefaktem
- Dla pliku HTML z grą: zawsze uwzględnij canvas, requestAnimationFrame, pętlę gry
- Zawsze ostatni krok = testy (lub weryfikacja kompletności)
- file = plik który krok modyfikuje/tworzy
"""

# Stała nazwa pliku stanu
STATE_FILENAME = "plan_state.json"


# ── GŁÓWNA FUNKCJA PLAN ───────────────────────────────────────────────────────

def plan(task: str, context: str = "") -> dict:
    """
    Generuje plan implementacji. Kompatybilna z v1.

    Zwraca dict z kluczami: goal, steps, tests_file, notes, verification_type.
    Każdy step ma teraz dodatkowe pola: acceptance_criteria, checkpoint, depends_on.
    """
    prompt = SYSTEM_PROMPT
    if context:
        prompt += f"\n\nKontekst:\n{context}"
    prompt += f"\n\nZadanie:\n{task}"

    response = call_llm(prompt, temperature=0.1)

    # Wyciągnij JSON z odpowiedzi
    match = re.search(r'\{.*\}', response, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            return _enrich_plan(result)
        except json.JSONDecodeError:
            pass

    # Fallback: zwróć surową odpowiedź jako prosty plan
    lines = [l.strip() for l in response.splitlines() if l.strip() and not l.startswith("{")]
    steps = [
        {
            "id": i + 1,
            "title": l[:60],
            "description": l,
            "file": "main.py",
            "acceptance_criteria": ["Krok zaimplementowany", "Brak błędów składni"],
            "checkpoint": f"step_{i + 1}_done",
            "depends_on": [i] if i > 0 else [],
        }
        for i, l in enumerate(lines[:6])
    ]
    return {
        "goal": task,
        "steps": steps,
        "tests_file": "test_main.py",
        "notes": response[:200],
        "verification_type": "generic",
    }


def _enrich_plan(plan_dict: dict) -> dict:
    """Uzupełnij brakujące pola acceptance_criteria/checkpoint w każdym kroku."""
    for i, step in enumerate(plan_dict.get("steps", [])):
        if "acceptance_criteria" not in step or not step["acceptance_criteria"]:
            step["acceptance_criteria"] = [
                f"Plik '{step.get('file', 'main.py')}' istnieje i nie jest pusty",
                "Brak błędów składni",
            ]
        if "checkpoint" not in step:
            step["checkpoint"] = f"step_{step.get('id', i + 1)}_done"
        if "depends_on" not in step:
            step["depends_on"] = [step.get("id", i + 1) - 1] if i > 0 else []

    if "verification_type" not in plan_dict:
        # Zgadnij na podstawie rozszerzeń plików
        files = [s.get("file", "") for s in plan_dict.get("steps", [])]
        if any(f.endswith(".html") or f.endswith(".htm") for f in files):
            plan_dict["verification_type"] = "html"
        elif any(f.endswith(".js") for f in files):
            plan_dict["verification_type"] = "javascript"
        elif any(f.endswith(".py") for f in files):
            plan_dict["verification_type"] = "python"
        else:
            plan_dict["verification_type"] = "generic"

    return plan_dict


# ── PERSYSTENCJA STANU ────────────────────────────────────────────────────────

def save_state(plan_dict: dict, work_dir: Path, completed_step_ids: list[int]):
    """Zapisz stan planu do work_dir/plan_state.json."""
    state = {
        "plan": plan_dict,
        "completed_steps": completed_step_ids,
        "remaining_steps": [
            s["id"] for s in plan_dict.get("steps", [])
            if s["id"] not in completed_step_ids
        ],
    }
    state_path = work_dir / STATE_FILENAME
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state_path


def load_state(work_dir: Path) -> dict | None:
    """Załaduj stan z work_dir/plan_state.json. Zwraca None jeśli brak pliku."""
    state_path = work_dir / STATE_FILENAME
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def plan_resumed(task: str, work_dir: Path) -> tuple[dict, list[int]]:
    """
    Wznawia plan jeśli istnieje zapis stanu, inaczej generuje nowy.

    Zwraca (plan_dict, już_ukończone_step_ids).
    """
    state = load_state(work_dir)
    if state:
        completed = state.get("completed_steps", [])
        remaining = state.get("remaining_steps", [])
        print(f"[planner] Wznawiam plan — ukończone kroki: {completed}, pozostałe: {remaining}")
        return state["plan"], completed

    # Nowy plan
    work_dir.mkdir(parents=True, exist_ok=True)
    task_plan = plan(task)
    save_state(task_plan, work_dir, [])
    return task_plan, []


def format_step_for_log(step: dict) -> str:
    """Formatuj krok do wydruku w logu."""
    criteria = step.get("acceptance_criteria", [])
    criteria_str = "\n".join(f"    ✓ {c}" for c in criteria[:3])
    return (
        f"  {step['id']}. {step['title']} → {step.get('file', '?')}\n"
        f"     {step.get('description', '')[:80]}\n"
        f"  Kryteria:\n{criteria_str}"
    )
