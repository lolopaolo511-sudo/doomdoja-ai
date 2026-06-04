"""
manager/level_calibration.py — przesuwa progi EASY/MEDIUM/HARD na podstawie danych.

Algorytm:
  1. Wczytaj statystyki z LevelFeedback.get_stats()
  2. MEDIUM local rate >= HIGH_LOCAL_RATE → obniż MEDIUM threshold
     (MEDIUM działa lokalnie → może być traktowane jak EASY)
  3. MEDIUM local rate <= LOW_LOCAL_RATE  → podwyższ MEDIUM threshold
     (MEDIUM ciągle wymaga eskalacji → traktuj jak HARD)
  4. Zapisz nowe progi do level_calibration_state.json

Minimalna liczba próbek: MIN_SAMPLES (domyślnie 5)
Raport kalibracji: calibration_report() → str
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .level import (
    DEFAULT_MEDIUM_THRESHOLD,
    DEFAULT_HARD_THRESHOLD,
    LevelClassifier,
    _save_calibration,
    get_classifier,
)
from .level_feedback import LevelFeedback, get_feedback

logger = logging.getLogger("manager.level_calibration")

MIN_SAMPLES    = 5     # min. próbek per (level, backend) żeby kalibrować
HIGH_LOCAL_RATE = 0.80  # MEDIUM local rate > ta wartość → obniż MEDIUM próg
LOW_LOCAL_RATE  = 0.40  # MEDIUM local rate < ta wartość → podwyższ próg (treat as HARD)
CLOUD_UPLIFT    = 0.10  # cloud musi dodać min. 10pp rate żeby eskalacja miała sens

MAX_MEDIUM_DELTA = 2    # max zmiana progu MEDIUM w jednej kalibracji
MAX_HARD_DELTA   = 2    # max zmiana progu HARD w jednej kalibracji


@dataclass
class CalibrationReport:
    old_medium: int
    old_hard: int
    new_medium: int
    new_hard: int
    changes: list[str] = field(default_factory=list)
    stats_used: dict = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [
            "╔══════════════════════════════════════════════════╗",
            "║     Level Calibration Report                   ║",
            "╚══════════════════════════════════════════════════╝",
            f"  Progi PRZED: MEDIUM≥{self.old_medium} HARD≥{self.old_hard}",
            f"  Progi PO:    MEDIUM≥{self.new_medium} HARD≥{self.new_hard}",
        ]
        if self.changes:
            lines.append("\n  Zmiany:")
            for c in self.changes:
                lines.append(f"    • {c}")
        else:
            lines.append("\n  Brak zmian (dane nie przekraczają progów kalibracji)")

        # Pokaż statystyki
        if self.stats_used:
            lines.append("\n  Dane (level/backend):")
            for level in ("EASY", "MEDIUM", "HARD"):
                if level not in self.stats_used:
                    continue
                for backend, d in self.stats_used[level].items():
                    rate = f"{d['rate']:.0%}" if d["rate"] is not None else "n/a"
                    lines.append(
                        f"    {level:6}/{backend:5}: "
                        f"n={d['total']:3}  sukces={d['success']:3}  "
                        f"rate={rate}  avg_rounds={d.get('avg_rounds','?')}"
                    )
        return "\n".join(lines)


def run_calibration(
    feedback: LevelFeedback | None = None,
    clf: LevelClassifier | None = None,
    dry_run: bool = False,
) -> CalibrationReport:
    """
    Przeprowadź kalibrację i (opcjonalnie) zapisz nowe progi.

    Args:
        feedback: instancja LevelFeedback (default: singleton)
        clf:      instancja LevelClassifier (default: singleton)
        dry_run:  True = tylko oblicz, nie zapisuj

    Returns:
        CalibrationReport z opisem zmian
    """
    fb  = feedback or get_feedback()
    clf = clf      or get_classifier()

    stats = fb.get_stats()
    old_medium = clf.medium_threshold
    old_hard   = clf.hard_threshold
    new_medium = old_medium
    new_hard   = old_hard
    changes: list[str] = []

    # ── Analiza MEDIUM ────────────────────────────────────────────────────────
    medium_local = stats.get("MEDIUM", {}).get("local", {})
    medium_cloud = stats.get("MEDIUM", {}).get("cloud", {})

    ml_total = medium_local.get("total", 0)
    mc_total = medium_cloud.get("total", 0)
    ml_rate  = medium_local.get("rate")
    mc_rate  = medium_cloud.get("rate")

    if ml_total >= MIN_SAMPLES and ml_rate is not None:
        if ml_rate >= HIGH_LOCAL_RATE:
            # MEDIUM działa lokalnie świetnie → obniż próg MEDIUM (więcej trafia jako EASY)
            delta = min(1, MAX_MEDIUM_DELTA)
            new_medium = max(2, old_medium - delta)
            changes.append(
                f"MEDIUM local rate={ml_rate:.0%} ≥ {HIGH_LOCAL_RATE:.0%} "
                f"→ obniż próg MEDIUM {old_medium} → {new_medium} "
                f"(więcej zadań jako EASY/local)"
            )
        elif ml_rate <= LOW_LOCAL_RATE:
            # MEDIUM ciągle failuje lokalnie → podwyższ próg HARD (traktuj MEDIUM jak HARD)
            delta = min(1, MAX_HARD_DELTA)
            new_hard = max(new_medium + 1, old_hard - delta)
            changes.append(
                f"MEDIUM local rate={ml_rate:.0%} ≤ {LOW_LOCAL_RATE:.0%} "
                f"→ obniż próg HARD {old_hard} → {new_hard} "
                f"(więcej zadań jako HARD/escalate)"
            )

    # ── Analiza cloud uplift dla MEDIUM ───────────────────────────────────────
    if ml_total >= MIN_SAMPLES and mc_total >= MIN_SAMPLES:
        if ml_rate is not None and mc_rate is not None:
            uplift = mc_rate - ml_rate
            if uplift < CLOUD_UPLIFT and ml_rate >= 0.60:
                changes.append(
                    f"MEDIUM cloud uplift={uplift:+.0%} < {CLOUD_UPLIFT:.0%} "
                    f"i local rate={ml_rate:.0%} — eskalacja nie przynosi wartości"
                )

    # ── Analiza EASY (sanity check) ───────────────────────────────────────────
    easy_local = stats.get("EASY", {}).get("local", {})
    el_total = easy_local.get("total", 0)
    el_rate  = easy_local.get("rate")
    if el_total >= MIN_SAMPLES and el_rate is not None and el_rate < 0.60:
        changes.append(
            f"⚠  EASY local rate={el_rate:.0%} — uwaga: zadania EASY mają niską skuteczność "
            f"(rozważ sprawdzenie scoringu)"
        )

    report = CalibrationReport(
        old_medium=old_medium,
        old_hard=old_hard,
        new_medium=new_medium,
        new_hard=new_hard,
        changes=changes,
        stats_used=stats,
    )

    if not dry_run and (new_medium != old_medium or new_hard != old_hard):
        clf.update_thresholds(new_medium, new_hard)
        logger.info(
            f"[calibration] Progi zmienione: "
            f"MEDIUM {old_medium}→{new_medium} HARD {old_hard}→{new_hard}"
        )

    return report
