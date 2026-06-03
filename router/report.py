"""
router/report.py — raport skuteczności routera per backend i klasa zadań.

Generuje tekstowy lub JSON raport z:
  - pass-rate per (backend, task_class)
  - średnia liczba rund i czas
  - rekomendacje kalibracji
  - tabela szczegółowa

Użycie:
    python3 router/report.py                # raport tekstowy na stdout
    python3 router/report.py --json         # raport JSON
    python3 router/report.py --mock         # demo z przykładowymi danymi
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from router.feedback import RouterFeedback
from router.calibration import calibrate, CalibrationResult


def _bar(rate: float | None, width: int = 12) -> str:
    """Prosty ASCII pasek procentowy."""
    if rate is None:
        return " " * width + "n/a"
    filled = round(rate * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {rate:5.1%}"


def generate_report(stats: dict, calibration: CalibrationResult) -> str:
    """Wygeneruj czytelny raport tekstowy."""
    lines = [
        "",
        "╔══════════════════════════════════════════════════════════╗",
        "║        ROUTER FEEDBACK — Raport skuteczności            ║",
        "╚══════════════════════════════════════════════════════════╝",
    ]

    if not stats:
        lines.append("\n  Brak danych historycznych.")
        lines.append("  Zarejestruj decyzje routera (RouterFeedback.record_outcome)")
        return "\n".join(lines)

    all_classes = sorted(set(
        cls for backend_data in stats.values() for cls in backend_data
    ))

    # ── Tabela per klasa ────────────────────────────────────────────────
    lines.append(f"\n  {'Klasa zadań':<14} {'Backend':<8} {'N':>4} {'Rate':<22} {'Avg rounds':>10} {'Avg czas':>9}")
    lines.append("  " + "─" * 72)

    for task_class in all_classes:
        first = True
        for backend in ("local", "cloud"):
            d = stats.get(backend, {}).get(task_class)
            if not d:
                continue
            cls_label = task_class if first else ""
            first = False
            bar = _bar(d.get("rate"))
            n = d.get("total", 0)
            avg_r = d.get("avg_rounds", "n/a")
            avg_t = d.get("avg_duration_s", "n/a")
            override = calibration.task_class_overrides.get(task_class, "")
            flag = f" ← {override}" if override and backend == "local" else ""
            lines.append(
                f"  {cls_label:<14} {backend:<8} {n:>4}  {bar}  "
                f"{str(avg_r):>10}r  {str(avg_t):>7}s{flag}"
            )
        lines.append("")

    # ── Sumaryczne liczby ───────────────────────────────────────────────
    total_decisions = sum(
        d.get("total", 0)
        for bd in stats.values() for d in bd.values()
    )
    local_total = sum(d.get("total", 0) for d in stats.get("local", {}).values())
    cloud_total = sum(d.get("total", 0) for d in stats.get("cloud", {}).values())

    lines += [
        "  " + "─" * 72,
        f"  Łącznie decyzji : {total_decisions}",
        f"  Local / Cloud   : {local_total} / {cloud_total}",
        "",
    ]

    # ── Kalibracja ──────────────────────────────────────────────────────
    lines += [
        "  ── Kalibracja ────────────────────────────────────────────────",
        f"  Próg złożoności   : {calibration.complexity_threshold}",
        f"  Eskalacja po N fail: {calibration.verifier_escalate}",
        "",
    ]
    for adj in calibration.adjustments:
        lines.append(f"  • {adj}")

    lines.append("")
    return "\n".join(lines)


def generate_json_report(stats: dict, calibration: CalibrationResult) -> dict:
    return {
        "stats": stats,
        "calibration": {
            "complexity_threshold": calibration.complexity_threshold,
            "verifier_escalate": calibration.verifier_escalate,
            "adjustments": calibration.adjustments,
            "task_class_overrides": calibration.task_class_overrides,
        },
    }


# ── Mock data dla demo ────────────────────────────────────────────────────────

MOCK_STATS = {
    "local": {
        "simple": {"total": 24, "success": 22, "fail": 2, "rate": 0.917,
                   "avg_rounds": 1.1, "avg_duration_s": 8.3},
        "medium": {"total": 18, "success": 13, "fail": 5, "rate": 0.722,
                   "avg_rounds": 1.8, "avg_duration_s": 18.7},
        "complex": {"total": 9, "success": 3, "fail": 6, "rate": 0.333,
                    "avg_rounds": 2.8, "avg_duration_s": 45.2},
        "private": {"total": 7, "success": 6, "fail": 1, "rate": 0.857,
                    "avg_rounds": 1.3, "avg_duration_s": 11.4},
        "escalated": {"total": 5, "success": 1, "fail": 4, "rate": 0.200,
                      "avg_rounds": 3.0, "avg_duration_s": 72.1},
    },
    "cloud": {
        "medium": {"total": 6, "success": 5, "fail": 1, "rate": 0.833,
                   "avg_rounds": 1.2, "avg_duration_s": 9.1},
        "complex": {"total": 8, "success": 7, "fail": 1, "rate": 0.875,
                    "avg_rounds": 1.4, "avg_duration_s": 14.5},
        "escalated": {"total": 5, "success": 4, "fail": 1, "rate": 0.800,
                      "avg_rounds": 1.6, "avg_duration_s": 18.2},
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Router feedback report")
    parser.add_argument("--json", action="store_true", help="Wynik jako JSON")
    parser.add_argument("--mock", action="store_true",
                        help="Użyj przykładowych danych (demo)")
    args = parser.parse_args()

    if args.mock:
        stats = MOCK_STATS
        print("  [MOCK] Używam przykładowych danych historycznych\n")
    else:
        fb = RouterFeedback()
        stats = fb.get_stats()

    calibration = calibrate(stats)

    if args.json:
        print(json.dumps(generate_json_report(stats, calibration),
                         ensure_ascii=False, indent=2))
    else:
        print(generate_report(stats, calibration))
    return 0


if __name__ == "__main__":
    sys.exit(main())
