#!/usr/bin/env python3
"""
manager/report.py — raport skuteczności per poziom/backend.

Użycie:
  python3 ~/qwen-agent/manager/report.py
  python3 ~/qwen-agent/manager/report.py --calibrate   # pokaż + uruchom kalibrację
  python3 ~/qwen-agent/manager/report.py --dry-run     # pokaż bez zapisu
  python3 ~/qwen-agent/manager/report.py --json        # JSON zamiast tabel
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _bar(rate: float | None, width: int = 20) -> str:
    if rate is None:
        return "·" * width
    filled = round(rate * width)
    return "█" * filled + "░" * (width - filled)


def print_report(stats: dict, clf_medium: int, clf_hard: int) -> None:
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║          Manager — Raport skuteczności                 ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Progi: EASY<{clf_medium}  MEDIUM<{clf_hard}  HARD≥{clf_hard}\n")

    if not stats:
        print("  (brak danych — uruchom kilka zadań przez daemon)")
        return

    header = f"  {'Poziom':<8} {'Backend':<7} {'n':>4}  {'Sukces':>6}  {'Rate':>5}  {'Bar':<22}  {'Avg rund':>8}  {'Avg t':>6}"
    print(header)
    print("  " + "─" * 72)

    for level in ("EASY", "MEDIUM", "HARD"):
        if level not in stats:
            continue
        for backend in ("local", "cloud"):
            if backend not in stats[level]:
                continue
            d = stats[level][backend]
            rate = d["rate"]
            rate_str = f"{rate:.0%}" if rate is not None else "  n/a"
            bar = _bar(rate)
            rounds = d.get("avg_rounds") or "?"
            dur = d.get("avg_duration_s") or "?"
            icon = {"EASY": "🟢", "MEDIUM": "🟡", "HARD": "🔴"}.get(level, "  ")
            backend_icon = "🏠" if backend == "local" else "☁️ "
            print(
                f"  {icon} {level:<6} {backend_icon}{backend:<5} "
                f"{d['total']:>4}  {d['success']:>6}  {rate_str:>5}  "
                f"{bar:<22}  {str(rounds):>8}  {str(dur):>6}s"
            )
        print()

    # Podsumowanie
    total_local = sum(
        stats.get(lvl, {}).get("local", {}).get("total", 0)
        for lvl in ("EASY", "MEDIUM", "HARD")
    )
    total_cloud = sum(
        stats.get(lvl, {}).get("cloud", {}).get("total", 0)
        for lvl in ("EASY", "MEDIUM", "HARD")
    )
    total_all = total_local + total_cloud
    if total_all > 0:
        pct_local = total_local / total_all
        print(f"  Łącznie: {total_all} zadań  |  🏠 local {total_local} ({pct_local:.0%})  |  ☁️  cloud {total_cloud} ({1-pct_local:.0%})")
    print()


def main():
    parser = argparse.ArgumentParser(description="Raport skuteczności managera")
    parser.add_argument("--calibrate", action="store_true", help="Uruchom kalibrację po raporcie")
    parser.add_argument("--dry-run", action="store_true", help="Kalibracja bez zapisu")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Wyjście JSON")
    args = parser.parse_args()

    from manager.level_feedback import get_feedback
    from manager.level import get_classifier
    from manager.level_calibration import run_calibration

    fb  = get_feedback()
    clf = get_classifier()
    stats = fb.get_stats()

    if args.json_out:
        out = {
            "stats": stats,
            "thresholds": {
                "medium": clf.medium_threshold,
                "hard": clf.hard_threshold,
            }
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print_report(stats, clf.medium_threshold, clf.hard_threshold)

    if args.calibrate or args.dry_run:
        print("\n─── Kalibracja ───")
        cal_report = run_calibration(dry_run=args.dry_run)
        print(cal_report)
        if args.dry_run:
            print("\n(tryb dry-run — progi NIE zostały zapisane)")


if __name__ == "__main__":
    main()
