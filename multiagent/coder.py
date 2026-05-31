#!/usr/bin/env python3
"""
ROLA: Coder
Implementuje każdy krok z planu i zapisuje pliki.
"""

import re
from pathlib import Path
from llm import call_llm

SYSTEM_PROMPT = """Jesteś programistą Python piszącym czysty, działający kod.

Implementujesz JEDEN konkretny krok zadania.
Zwróć TYLKO blok kodu Python bez wyjaśnień, otoczony znacznikami:

```python
# kod tutaj
```

Zasady:
- Pisz pełny, działający kod
- Brak zbędnych komentarzy
- Nie pisz instrukcji użycia ani README
- Jeśli modyfikujesz istniejący plik, napisz PEŁNĄ zawartość pliku
"""


def implement_step(step: dict, existing_code: str = "", context: str = "") -> str:
    prompt = SYSTEM_PROMPT
    if context:
        prompt += f"\n\nKontekst projektu:\n{context}"
    if existing_code:
        prompt += f"\n\nObecna zawartość pliku '{step.get('file', 'main.py')}':\n```python\n{existing_code}\n```"
    prompt += f"\n\nKrok do implementacji:\nTytuł: {step['title']}\nOpis: {step['description']}\nPlik: {step.get('file', 'main.py')}"

    response = call_llm(prompt, temperature=0.15)

    # Wyciągnij blok kodu
    match = re.search(r'```python\n(.*?)```', response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: cała odpowiedź jako kod
    clean = re.sub(r'```[a-z]*\n?', '', response).strip()
    return clean


def write_code(file_path: Path, code: str):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(code)


def implement_all_steps(plan: dict, work_dir: Path) -> dict[str, str]:
    """Implementuje wszystkie kroki, zwraca dict {plik: kod}."""
    results = {}
    context = f"Cel: {plan.get('goal', '')}\nUwagi: {plan.get('notes', '')}"

    for step in plan.get("steps", []):
        fname = step.get("file", "main.py")
        fpath = work_dir / fname
        existing = fpath.read_text() if fpath.exists() else ""

        print(f"  [coder] Krok {step['id']}: {step['title']} → {fname}")
        code = implement_step(step, existing, context)
        write_code(fpath, code)
        results[fname] = code

    return results
