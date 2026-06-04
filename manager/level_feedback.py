"""
manager/level_feedback.py — zapis i odczyt wyników per poziom EASY/MEDIUM/HARD.

Każde przetworzone zadanie zapisuje wpis do memory2 episodic z polami:
  level, backend, model, verifier_passed, rounds, duration_s, task_preview

Dane te są następnie używane przez level_calibration.py do przesuwania progów.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger("manager.level_feedback")

TAGS_BASE = ["manager", "level_feedback"]


def _get_memory():
    """Lazy import Memory2 — nie crashuje jeśli niedostępna."""
    try:
        from memory2.memory2 import Memory2
        return Memory2()
    except Exception as e:
        logger.debug(f"memory2 niedostępna: {e}")
        return None


class LevelFeedback:
    """Zapisuje i odczytuje historię wyników per poziom trudności."""

    def __init__(self):
        self._mem = _get_memory()

    def record(
        self,
        task_id: str,
        task_preview: str,
        level: str,          # EASY | MEDIUM | HARD
        backend: str,        # local | cloud
        model: str,
        verifier_passed: bool,
        rounds: int,
        duration_s: float,
        escalated: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Zapisz wynik zadania do memory2."""
        if not self._mem:
            return

        outcome = "success" if verifier_passed and not error else "fail"
        content = (
            f"Manager:{level} | {outcome} | {backend}/{model} | "
            f"rounds={rounds} t={duration_s:.1f}s | {task_preview[:60]}"
        )
        tags = TAGS_BASE + [level, backend, outcome]
        if escalated:
            tags.append("escalated")

        meta = {
            "task_id": task_id,
            "level": level,
            "backend": backend,
            "model": model,
            "verifier_passed": verifier_passed,
            "rounds": rounds,
            "duration_s": duration_s,
            "escalated": escalated,
            "outcome": outcome,
            "error": error,
            "recorded_at": datetime.now().isoformat(),
        }
        try:
            self._mem.remember("episodic", content, tags=tags, meta=meta)
            logger.debug(f"[level_feedback] recorded {task_id} level={level} outcome={outcome}")
        except Exception as e:
            logger.debug(f"[level_feedback] zapis błąd: {e}")

    def get_stats(self, limit: int = 500) -> dict[str, dict]:
        """
        Zwraca statystyki per (level, backend):
          {
            "EASY":   {"local":  {"total":N, "success":M, "rate":0.95, ...}},
            "MEDIUM": {"local":  {...}, "cloud": {...}},
            "HARD":   {"cloud":  {...}},
          }
        """
        if not self._mem:
            return {}

        try:
            hits = self._mem.recall(
                "Manager:", type="episodic", top_k=limit,
                tags=["manager", "level_feedback"],
            )
        except Exception as e:
            logger.debug(f"[level_feedback] recall błąd: {e}")
            return {}

        from collections import defaultdict
        stats: dict = defaultdict(
            lambda: defaultdict(
                lambda: {"total": 0, "success": 0, "fail": 0,
                         "escalated": 0, "rounds_sum": 0, "duration_sum": 0.0}
            )
        )

        for h in hits:
            meta = h.get("meta", {})
            level   = meta.get("level", "?")
            backend = meta.get("backend", "?")
            outcome = meta.get("outcome", "?")

            e = stats[level][backend]
            e["total"] += 1
            e["rounds_sum"] += meta.get("rounds", 1)
            e["duration_sum"] += meta.get("duration_s", 0.0)
            if meta.get("escalated"):
                e["escalated"] += 1
            if outcome == "success":
                e["success"] += 1
            elif outcome == "fail":
                e["fail"] += 1

        # Oblicz rate i średnie
        result: dict = {}
        for level, backends in stats.items():
            result[level] = {}
            for backend, d in backends.items():
                n = d["total"]
                result[level][backend] = {
                    "total": n,
                    "success": d["success"],
                    "fail": d["fail"],
                    "escalated": d["escalated"],
                    "rate": round(d["success"] / n, 3) if n > 0 else None,
                    "avg_rounds": round(d["rounds_sum"] / n, 1) if n > 0 else None,
                    "avg_duration_s": round(d["duration_sum"] / n, 1) if n > 0 else None,
                }
        return dict(result)


# Singleton
_default_fb: Optional[LevelFeedback] = None


def get_feedback() -> LevelFeedback:
    global _default_fb
    if _default_fb is None:
        _default_fb = LevelFeedback()
    return _default_fb
