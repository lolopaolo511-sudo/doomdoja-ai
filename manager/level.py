"""
manager/level.py — 3-poziomowy klasyfikator trudności zadania.

Poziomy:
  EASY   → lokalny model, bez eskalacji, bez sprawdzania verifierem
  MEDIUM → lokalny NAJPIERW; verifier sprawdza; po N failach → eskalacja cloud
  HARD   → od razu needs_escalation, bez marnowania rund lokalnie

Sygnały oceniane:
  1. Typ zadania        — mechaniczne/boilerplate vs analityczne/projektowe
  2. Zakres             — 1 plik/funkcja vs wiele plików/systemów
  3. Weryfikowalność    — jasny test pass/fail vs ocena subiektywna
  4. Kroki/zależności   — liniowe vs nieliniowe/wieloetapowe
  5. Nowość             — znany wzorzec vs innowacja/niestandardowe
  6. Stawka             — dev/test vs produkcja/live/migracja
  7. Kontekst           — małe zadanie vs wymaga całego projektu

Kalibracja:
  Progi MEDIUM_THRESHOLD i HARD_THRESHOLD mogą być przesuwane
  na podstawie danych z level_feedback.py. Plik kalibracji:
  manager/level_calibration_state.json
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger("manager.level")

Level = Literal["EASY", "MEDIUM", "HARD"]

# ── Stałe domyślne ────────────────────────────────────────────────────────────

DEFAULT_MEDIUM_THRESHOLD = 4   # score >= ta wartość → MEDIUM (zamiast EASY)
DEFAULT_HARD_THRESHOLD   = 7   # score >= ta wartość → HARD

CALIBRATION_STATE_FILE = Path(__file__).parent / "level_calibration_state.json"

# ── Słowniki sygnałów ─────────────────────────────────────────────────────────

# Typ zadania — mechaniczne / boilerplate → niski score
_MECHANICAL_KW = [
    "parser", "parsuj", "crud", "insert", "select", "update", "delete",
    "konwersj", "convert", "zmień nazwę", "rename", "szablon", "template",
    "boilerplate", "config", "konfiguracja", "dockerfile", "gitignore",
    "one-liner", "jednolinijkowy", "prosty skrypt", "simple script",
    "funkcja pomocnicza", "helper", "wrapper", "util", "narzędzie",
    "przelicz", "oblicz", "sformatuj", "format", "walidator", "validator",
    "dodaj komentarz", "docstring", "readme sekcja",
]

# Typ zadania — analityczne / projektowe → wysoki score
_ANALYTICAL_KW = [
    "architektur", "architecture", "zaprojektuj", "design",
    "oceń", "przeanalizuj", "porównaj", "compare", "evaluate",
    "strategia", "strategy", "roadmapa", "roadmap",
    "code review", "przejrzyj kod", "ocena kodu",
    "innowac", "nowe podejście", "niestandardow",
    "wymyśl", "zaproponuj", "recommendation",
]

# Zakres — wąski (1 plik/funkcja) → obniża score
_NARROW_SCOPE_KW = [
    "1 funkcja", "jedną funkcję", "pojedyncz", "single",
    "1 plik", "jeden plik", "this function", "ten plik",
    "small", "małą", "małe", "małą funkcję",
]

# Zakres — szeroki (wiele plików/systemów) → podwyższa score
_WIDE_SCOPE_KW = [
    "całość", "cały projekt", "wszystkie pliki", "wiele modułów",
    "whole project", "entire", "across files", "kilka plików",
    "system", "całą aplikacj", "full stack",
]

# Weryfikowalność — jest test/asercja → obniża score (łatwo sprawdzić)
_VERIFIABLE_KW = [
    "test", "pytest", "assert", "asercja", "sprawdź czy", "powinno zwrócić",
    "expected", "oczekiwan", "test case", "unit test", "tdd",
    "weryfikowalny", "pass/fail", "assertEqual",
]

# Weryfikowalność — subiektywna ocena → podwyższa score
_HARD_TO_VERIFY_KW = [
    "oceń", "ocena", "subiektywn", "lepsze podejście", "best practice",
    "opinia", "feedback", "przemyśl", "zaproponuj optymalizacj",
]

# Kroki/zależności — wiele etapów → podwyższa score
_MULTISTEP_KW = [
    "najpierw", "następnie", "potem", "krok po kroku", "etap 1",
    "wieloetapow", "multi-step", "pipeline", "workflow",
    "najpierw X, potem Y", "a następnie", "zrób X i Y i Z",
]

# Nowość — nieznane terytorium → podwyższa score
_NOVELTY_KW = [
    "nowy algorytm", "nie mamy jeszcze", "pierwszy raz", "nigdy wcześniej",
    "wymyśl od zera", "innowac", "novel", "from scratch",
    "niestandardowy", "custom protokół", "własny format",
]

# Stawka — produkcja/live → mocno podwyższa score
_HIGH_STAKES_KW = [
    "produkcja", "production", "live", "na produkcji", "klient czeka",
    "migracja bazy", "database migration", "breaking change",
    "publiczne api", "public api", "release", "deploy na prod",
    "nie możemy przerwać", "bez downtime",
]

# Kontekst — wymaga dużo kontekstu → podwyższa score
_LARGE_CONTEXT_KW = [
    "cały repo", "wszystkie moduły", "kontekst całego projektu",
    "przejrzyj wszystko", "read the whole", "pełen kontekst",
    "wiele zależności", "wiele klas",
]

# Privacy — wymusza EASY/LOCAL (bezpieczeństwo)
_PRIVACY_KW = [
    "hasł", "password", "secret", "token", "api_key", "pesel",
    "klucz api", "prywatny", "prywatne", "credential", "confidential",
    "private key", "ssh key", "bearer", "authorization",
]


# ── Dataclass wyniku ──────────────────────────────────────────────────────────

@dataclass
class LevelResult:
    level: Level
    score: int
    reason: str
    signals: list[str] = field(default_factory=list)
    privacy_forced: bool = False
    medium_threshold: int = DEFAULT_MEDIUM_THRESHOLD
    hard_threshold: int   = DEFAULT_HARD_THRESHOLD

    def summary(self) -> str:
        icon = {"EASY": "🟢", "MEDIUM": "🟡", "HARD": "🔴"}[self.level]
        sig = " | ".join(self.signals[:4]) if self.signals else "brak sygnałów"
        return f"{icon} {self.level} (score={self.score}) — {sig}"

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "score": self.score,
            "reason": self.reason,
            "signals": self.signals,
            "privacy_forced": self.privacy_forced,
        }


# ── Główna klasa klasyfikatora ────────────────────────────────────────────────

class LevelClassifier:
    """
    Klasyfikuje zadanie na EASY / MEDIUM / HARD.

    Użycie:
        clf = LevelClassifier()
        result = clf.classify("napisz parser CSV")
        print(result.summary())  # 🟢 EASY (score=1)

    Kalibracja ładuje się z CALIBRATION_STATE_FILE jeśli plik istnieje.
    """

    def __init__(
        self,
        medium_threshold: int = DEFAULT_MEDIUM_THRESHOLD,
        hard_threshold: int = DEFAULT_HARD_THRESHOLD,
    ):
        cal = _load_calibration()
        self.medium_threshold = cal.get("medium_threshold", medium_threshold)
        self.hard_threshold   = cal.get("hard_threshold",   hard_threshold)

    def classify(self, task: str) -> LevelResult:
        task_lower = task.lower()

        # 1. Privacy → EASY wymuszone
        for kw in _PRIVACY_KW:
            if kw in task_lower:
                return LevelResult(
                    level="EASY",
                    score=0,
                    reason=f"privacy: słowo '{kw}' — wymuś lokalnie",
                    signals=[f"privacy:{kw}"],
                    privacy_forced=True,
                    medium_threshold=self.medium_threshold,
                    hard_threshold=self.hard_threshold,
                )

        score, signals = self._score(task, task_lower)

        if score >= self.hard_threshold:
            level: Level = "HARD"
        elif score >= self.medium_threshold:
            level = "MEDIUM"
        else:
            level = "EASY"

        reason = (
            f"score={score} (EASY<{self.medium_threshold} "
            f"MEDIUM<{self.hard_threshold} HARD≥{self.hard_threshold})"
        )
        return LevelResult(
            level=level,
            score=score,
            reason=reason,
            signals=signals,
            medium_threshold=self.medium_threshold,
            hard_threshold=self.hard_threshold,
        )

    def _score(self, task: str, task_lower: str) -> tuple[int, list[str]]:
        score = 0
        signals: list[str] = []

        def _hit(kw_list: list[str], label: str, pts: int, cap: int) -> int:
            hits = [kw for kw in kw_list if kw in task_lower]
            if not hits:
                return 0
            added = min(len(hits) * pts, cap)
            signals.append(f"{label}:{','.join(hits[:2])}")
            return added

        # Typ zadania
        score -= _hit(_MECHANICAL_KW, "mech", 1, 2)      # max -2
        score += _hit(_ANALYTICAL_KW, "anal", 2, 4)       # max +4

        # Zakres
        score -= _hit(_NARROW_SCOPE_KW, "wąski", 1, 2)   # max -2
        score += _hit(_WIDE_SCOPE_KW, "szeroki", 2, 4)    # max +4

        # Weryfikowalność
        score -= _hit(_VERIFIABLE_KW, "werif", 1, 2)      # max -2
        score += _hit(_HARD_TO_VERIFY_KW, "trudwer", 2, 4) # max +4

        # Kroki / zależności
        score += _hit(_MULTISTEP_KW, "multistep", 1, 3)   # max +3

        # Nowość
        score += _hit(_NOVELTY_KW, "nowość", 3, 3)        # max +3

        # Stawka
        score += _hit(_HIGH_STAKES_KW, "stawka", 4, 4)    # max +4

        # Kontekst
        score += _hit(_LARGE_CONTEXT_KW, "kontekst", 2, 2) # max +2

        # Długość jako słaby sygnał złożoności
        if len(task) > 800:
            score += 2
            signals.append("długie>800")
        elif len(task) > 400:
            score += 1
            signals.append("długie>400")

        score = max(0, score)
        return score, signals

    def update_thresholds(self, medium: int, hard: int) -> None:
        """Aktualizuj progi (wywołuj po kalibracji)."""
        self.medium_threshold = medium
        self.hard_threshold   = hard
        _save_calibration({"medium_threshold": medium, "hard_threshold": hard})
        logger.info(f"[LevelClassifier] Progi zaktualizowane: MEDIUM≥{medium} HARD≥{hard}")


# ── Kalibracja ────────────────────────────────────────────────────────────────

def _load_calibration() -> dict:
    if CALIBRATION_STATE_FILE.exists():
        try:
            return json.loads(CALIBRATION_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_calibration(data: dict) -> None:
    CALIBRATION_STATE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Moduł-level API (shorthands) ──────────────────────────────────────────────

_default_clf: LevelClassifier | None = None


def get_classifier() -> LevelClassifier:
    global _default_clf
    if _default_clf is None:
        _default_clf = LevelClassifier()
    return _default_clf


def classify_level(task: str) -> LevelResult:
    """Shorthand — używa globalnego singletona klasyfikatora."""
    return get_classifier().classify(task)


# ── CLI debug ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    task_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "napisz funkcję Python"
    r = classify_level(task_text)
    print(r.summary())
    print(f"  sygnały: {r.signals}")
    print(f"  reason:  {r.reason}")
