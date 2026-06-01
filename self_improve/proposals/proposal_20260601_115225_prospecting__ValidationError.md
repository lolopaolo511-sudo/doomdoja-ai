# Propozycja poprawki

**Klaster:** `prospecting::ValidationError`
**Wystąpień:** 1
**Wygenerowane:** 2026-06-01T11:52:25.953503
**Status:** ⏳ DO REVIEW (nie auto-mergowane)

## Przykładowe błędy
- `ValidationError: budget field cannot be empty`

## Analiza LLM

ROOT_CAUSE: Błąd wynika z faktu, że pole "budget" jest puste podczas próby dostarczenia nowego joba do systemu.

SEVERITY: High

PROPOSAL_TYPE: code

DIFF_OR_PROMPT:
```diff
- def create_job(data):
+ def create_job(data):
     if not data.get('budget'):
         raise prospecting::ValidationError("budget field cannot be empty")
     # reszta logiki dotyczącej tworzenia joba
```

EXPLANATION: Dodanie sprawdzenia, czy pole "budget" jest wypełnione przed kontynuacją procesu tworzenia joba, zapobiega błędom i zapewnia poprawne działanie systemu. Sprawdzanie to ma niskie nakłady na modyfikację kodu i jest niezbędne do uniknięcia błędów w przyszłości.

---
*Wygenerowane przez self_improve/analyzer.py. Zatwierdź ręcznie przed wdrożeniem.*
