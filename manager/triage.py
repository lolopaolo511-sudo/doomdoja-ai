"""
triage.py — lekka klasyfikacja zadania: local vs escalate.

Reużywa logiki z router/router.py, ale nie inicjuje backendów LLM.
Przydatne do szybkich decyzji w CLI, testach lub preview przed wysłaniem.

Użycie:
    from manager.triage import classify_task

    decision = classify_task("napisz parser CSV")
    # → "local"

    decision, reason = classify_task("zaprojektuj architekturę", return_reason=True)
    # → ("escalate", "wysokie słowa kluczowe: architektura")
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Prywatne słowa wymuszające local — NIGDY do chmury
_PRIVACY_KEYWORDS = [
    "hasł", "password", "secret", "token", "api_key", "pesel",
    "klucz api", "prywatny", "prywatne", "credential", "confidential",
    "konfidencjonalne", "private key", "ssh key", "bearer", "authorization",
]

# Słowa sugerujące niską złożoność (→ local)
_LOW_KEYWORDS = [
    "prosty", "simple", "szybki skrypt", "quick script", "jednolinijkowy",
    "one-liner", "print", "konwersj", "convert", "zmień nazwę", "rename",
    "parser", "crud", "test", "fixture", "docstring", "komentarz",
    "config", "szablon", "template", "przelicz", "skrypt bash",
]

# Słowa sugerujące wysoką złożoność (→ escalate)
_HIGH_KEYWORDS = [
    "cała aplikac", "full application", "architektur", "architecture",
    "refactor", "refaktoryzac", "system", "integrac", "integration",
    "debug", "wielowątkow", "concurrent", "async", "danych", "database",
    "deployment", "wdrożen", "optymalizac", "optimization", "skomplikow",
    "complex", "migracja", "produkcja", "production", "zaprojektuj",
    "oceń", "przeanalizuj całość", "race condition", "memory leak",
]

# Długość zadania powyżej której +1 punkt
_LEN_THRESHOLD = 500
# Próg wyniku: >= ta wartość → escalate
_ESCALATE_THRESHOLD = 6


def classify_task(
    task: str,
    verifier_fails: int = 0,
    return_reason: bool = False,
) -> "str | tuple[str, str]":
    """
    Klasyfikuje zadanie jako "local" lub "escalate".

    Args:
        task:            Treść zadania.
        verifier_fails:  Liczba nieudanych rund verifier dla tego zadania.
        return_reason:   Jeśli True, zwraca (decision, reason) zamiast samego stringa.

    Returns:
        "local" lub "escalate" (albo tuple jeśli return_reason=True).
    """
    task_lower = task.lower()

    # 1. Privacy check — zawsze local
    for kw in _PRIVACY_KEYWORDS:
        if kw in task_lower:
            reason = f"privacy-protected: słowo '{kw}' wykryte — wymuś local"
            return ("local", reason) if return_reason else "local"

    # 2. Verifier escalation — za dużo failów
    if verifier_fails >= 2:
        reason = f"eskalacja: {verifier_fails} nieudanych rund verifier"
        return ("escalate", reason) if return_reason else "escalate"

    # 3. Oblicz wynik złożoności
    score, score_reason = _score_task(task, task_lower)

    decision = "escalate" if score >= _ESCALATE_THRESHOLD else "local"
    return (decision, score_reason) if return_reason else decision


def _score_task(task: str, task_lower: str) -> tuple[int, str]:
    """Oblicza wynik złożoności 0–10 i zwraca (score, reason)."""
    reasons: list[str] = []
    score = 0

    # Długość zadania
    if len(task) > _LEN_THRESHOLD * 2:
        score += 2
        reasons.append(f"bardzo długie zadanie ({len(task)} znaków)")
    elif len(task) > _LEN_THRESHOLD:
        score += 1
        reasons.append(f"długie zadanie ({len(task)} znaków)")

    # Wysokie słowa kluczowe — max 5 punktów
    high_hits = [kw for kw in _HIGH_KEYWORDS if kw in task_lower]
    hit_pts = min(len(high_hits), 5)
    if hit_pts:
        score += hit_pts
        reasons.append(f"wysokie słowa: {', '.join(high_hits[:3])}")

    # Niskie słowa kluczowe — max -2 punkty
    low_hits = [kw for kw in _LOW_KEYWORDS if kw in task_lower]
    low_pts = min(len(low_hits), 2)
    if low_pts:
        score -= low_pts
        reasons.append(f"niskie słowa: {', '.join(low_hits[:3])}")

    score = max(0, min(score, 10))
    reason = (
        f"score={score}/{_ESCALATE_THRESHOLD}  "
        + ("; ".join(reasons) if reasons else "brak specjalnych sygnałów")
    )
    return score, reason


def explain(task: str, verifier_fails: int = 0) -> str:
    """Zwraca czytelne wyjaśnienie decyzji triażu (do debugowania/CLI)."""
    decision, reason = classify_task(task, verifier_fails=verifier_fails, return_reason=True)
    icon = "🏠 LOCAL" if decision == "local" else "☁️  ESCALATE"
    return f"{icon}  |  {reason}"


# ── Używaj przez router gdy dostępny (pełna logika z config.yaml) ─────────────

def classify_task_full(task: str, verifier_fails: int = 0) -> tuple[str, str]:
    """
    Klasyfikacja z pełną logiką routera (czyta config.yaml).
    Wolniejsza niż classify_task(), ale spójna ze środowiskiem runtime.
    """
    try:
        from router import HybridRouter, RouterContext
        router = HybridRouter()
        ctx = RouterContext(
            step_title=task[:80],
            verifier_fails=verifier_fails,
        )
        decision = router.choose_model(task, ctx)
        return decision.backend, decision.reason
    except Exception as exc:
        # Fallback na lekką implementację
        return classify_task(task, verifier_fails=verifier_fails, return_reason=True)  # type: ignore


# ── CLI debug ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    task_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "napisz funkcję Python"
    print(explain(task_text))
    decision, reason = classify_task_full(task_text)
    print(f"\n[router pełny] {'🏠 LOCAL' if decision == 'local' else '☁️  ESCALATE'} | {reason}")
