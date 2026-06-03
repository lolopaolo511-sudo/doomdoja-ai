# Kandydat do zatwierdzenia

**Komponent:** `evals/fizzbuzz`
**Błąd:** `fizzbuzz(15) zwraca 14 elem`
**Wygenerowane:** 2026-06-03T07:40:05.478380
**Status:** ⏳ DO REVIEW — NIE merguj bez zatwierdzenia człowieka

## Wyniki Eval

| Metryka | Wartość |
|---------|---------|
| Eval przed patchem | 0.0% |
| Eval po patchu | 100.0% |
| Delta | **+100.0pp** |
| Poprawione zadania | swe_fix_offbyone |
| Regresje |  |

## Root Cause

range(1, n) off-by-one

## Propozycja zmiany (code)

```
def fizzbuzz(n):
    result = []
    for i in range(1, n + 1):
        if i % 15 == 0: result.append("FizzBuzz")
        elif i % 3 == 0: result.append("Fizz")
        elif i % 5 == 0: result.append("Buzz")
        else: result.append(str(i))
    return result
```

## Wyjaśnienie

Zmień n na n+1.

---
*Wygenerowane przez self_improve/closed_loop.py. Zatwierdź ręcznie przed wdrożeniem.*
*Plik: candidate_20260603_074005_evals_fizzbuzz.md*
