"""
router/feedback.py — zapisuje decyzje routera do pamięci epizodycznej (memory2).

Każda decyzja router → wpis w episodic memory z polami:
  backend, model, task_class, outcome, rounds, duration_s, score

Dane te są następnie używane przez calibration.py do dostrajania progów.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _get_memory() -> "object | None":
    """Lazy import Memory2 — nie crashuje jeśli niedostępna."""
    try:
        from memory2.memory2 import Memory2
        return Memory2()
    except Exception:
        return None


def _classify_task(score: int, privacy: bool, escalated: bool) -> str:
    """Klasyfikuj zadanie na podstawie sygnałów routera."""
    if privacy:
        return "private"
    if escalated:
        return "escalated"
    if score <= 2:
        return "simple"
    if score >= 6:
        return "complex"
    return "medium"


class RouterFeedback:
    """
    Zapisuje i odczytuje historię decyzji routera z memory2 episodic.
    Bezpieczny (nie crashuje) gdy memory2 niedostępna.
    """

    TAGS = ["router", "feedback"]

    def __init__(self):
        self._mem = _get_memory()
        self._pending: dict[str, dict] = {}  # session_id → partial data

    # ── Zapis decyzji ────────────────────────────────────────────────────────

    def log_decision(
        self,
        session_id: str,
        task_preview: str,
        backend: str,
        model: str,
        score: int,
        privacy: bool,
        escalated: bool,
    ) -> None:
        """Loguj decyzję routera do memory2 episodic."""
        if not self._mem:
            return
        task_class = _classify_task(score, privacy, escalated)
        # Przechowaj dane tymczasowo — outcome dopiero po zakończeniu zadania
        self._pending[session_id] = {
            "task_preview": task_preview[:80],
            "backend": backend,
            "model": model,
            "score": score,
            "task_class": task_class,
            "privacy": privacy,
            "escalated": escalated,
            "start_ts": datetime.now().isoformat(),
        }

    def record_outcome(
        self,
        session_id: str,
        outcome: str,       # "success" | "fail" | "error"
        rounds: int = 1,
        duration_s: float = 0.0,
    ) -> None:
        """
        Zapisz wynik zadania — łączy z wcześniejszą decyzją i zapisuje do memory2.
        Wywołaj po zakończeniu zadania.
        """
        if not self._mem:
            return
        data = self._pending.pop(session_id, None)
        if not data:
            # Brak wcześniejszej decyzji — zapisz sam wynik
            data = {"task_preview": f"session:{session_id}", "backend": "unknown",
                    "model": "unknown", "score": 0, "task_class": "unknown",
                    "privacy": False, "escalated": False,
                    "start_ts": datetime.now().isoformat()}
        content = (
            f"Router: {data['backend']}/{data['model']} → "
            f"[{data['task_class']}] score={data['score']} | "
            f"rounds={rounds} | {duration_s:.1f}s | {outcome} | "
            f"task: {data['task_preview']}"
        )
        try:
            self._mem.remember(
                "episodic",
                content,
                tags=self.TAGS + [data["task_class"], data["backend"]],
                meta={
                    "task_id": session_id,
                    "outcome": outcome,
                    "backend": data["backend"],
                    "model": data["model"],
                    "task_class": data["task_class"],
                    "score": data["score"],
                    "rounds": rounds,
                    "duration_s": duration_s,
                    "privacy": data["privacy"],
                    "escalated": data["escalated"],
                },
            )
        except Exception as e:
            pass  # nie przerywaj pracy agenta z powodu błędu pamięci

    def get_history(self, limit: int = 200) -> list[dict]:
        """Pobierz historię decyzji routera z memory2."""
        if not self._mem:
            return []
        try:
            hits = self._mem.recall("Router:", type="episodic", top_k=limit,
                                     tags=["router"])
            return [h for h in hits if "Router:" in h.get("content", "")]
        except Exception:
            return []

    def get_stats(self) -> dict:
        """
        Oblicz statystyki skuteczności per (backend, task_class).
        Zwraca:
          {
            "local": {"simple": {"total": N, "success": M, "rate": 0.9}, ...},
            "cloud": {...},
          }
        """
        history = self.get_history()
        from collections import defaultdict
        stats: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(
            lambda: {"total": 0, "success": 0, "fail": 0,
                     "rounds_sum": 0, "duration_sum": 0.0}
        ))
        for h in history:
            meta = h.get("meta", {})
            backend = meta.get("backend", "unknown")
            task_class = meta.get("task_class", "unknown")
            outcome = meta.get("outcome", "unknown")
            rounds = meta.get("rounds", 1)
            duration = meta.get("duration_s", 0.0)

            entry = stats[backend][task_class]
            entry["total"] += 1
            entry["rounds_sum"] += rounds
            entry["duration_sum"] += duration
            if outcome == "success":
                entry["success"] += 1
            elif outcome == "fail":
                entry["fail"] += 1

        # Oblicz rate i średnie
        result: dict = {}
        for backend, classes in stats.items():
            result[backend] = {}
            for cls, d in classes.items():
                total = d["total"]
                result[backend][cls] = {
                    "total": total,
                    "success": d["success"],
                    "fail": d["fail"],
                    "rate": round(d["success"] / total, 3) if total > 0 else None,
                    "avg_rounds": round(d["rounds_sum"] / total, 1) if total > 0 else None,
                    "avg_duration_s": round(d["duration_sum"] / total, 1) if total > 0 else None,
                }
        return dict(result)
