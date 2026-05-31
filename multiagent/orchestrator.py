#!/usr/bin/env python3
"""
Orkiestrator multi-agenta: Planner → Coder → Reviewer → (poprawki) → DONE
Użycie: python3 orchestrator.py "zadanie" [--work-dir /tmp/projekt] [--max-rounds 2]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Dodaj katalog multi-agenta do path
sys.path.insert(0, str(Path(__file__).parent))
from planner import plan
from coder import implement_all_steps
from reviewer import review, run_tests


def log(msg: str, role: str = ""):
    prefix = f"[{role.upper():8}]" if role else "[        ]"
    print(f"{prefix} {msg}")


def orchestrate(task: str, work_dir: Path, max_rounds: int = 2) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now().isoformat()

    # ── ROLA 1: PLANNER ──────────────────────────────────────────────
    log(f"Analizuję zadanie: {task[:80]}", "planner")
    task_plan = plan(task)
    log(f"Cel: {task_plan.get('goal', '?')}", "planner")
    log(f"Kroków: {len(task_plan.get('steps', []))}", "planner")
    for s in task_plan.get("steps", []):
        log(f"  {s['id']}. {s['title']} → {s.get('file', '?')}", "planner")

    # ── ROLA 2: CODER (z pętlą poprawek) ─────────────────────────────
    code_files = {}
    review_result = {"approved": False, "issues": [], "fixes": ""}

    for round_num in range(1, max_rounds + 1):
        log(f"Runda implementacji {round_num}/{max_rounds}", "coder")

        if round_num > 1 and review_result.get("fixes"):
            # Poprawki od reviewera trafiają jako dodatkowy krok
            log(f"Implementuję poprawki z review", "coder")
            fix_step = {
                "id": 99,
                "title": "Poprawki z code review",
                "description": review_result["fixes"],
                "file": list(code_files.keys())[0] if code_files else "main.py",
            }
            from coder import implement_step, write_code
            for fname, code in list(code_files.items()):
                fix_code = implement_step(fix_step, code)
                fpath = work_dir / fname
                write_code(fpath, fix_code)
                code_files[fname] = fix_code
        else:
            code_files = implement_all_steps(task_plan, work_dir)

        # ── ROLA 3: REVIEWER ─────────────────────────────────────────
        log("Uruchamiam testy...", "reviewer")
        tests_ok, test_output = run_tests(work_dir)
        log(f"Testy: {'PASS ✓' if tests_ok else 'FAIL ✗'}", "reviewer")
        if test_output:
            for line in test_output.splitlines()[-8:]:
                log(f"  {line}", "reviewer")

        log("Przeglądam kod...", "reviewer")
        review_result = review(task_plan, code_files, test_output)

        if review_result["approved"] and tests_ok:
            log("APPROVED ✓ — kod zatwierdiony", "reviewer")
            break
        else:
            if review_result["issues"]:
                log(f"Znalezione problemy ({len(review_result['issues'])}):", "reviewer")
                for issue in review_result["issues"][:5]:
                    log(f"  {issue}", "reviewer")
            if round_num < max_rounds:
                log("Zlecam poprawki coderowi...", "reviewer")

    # ── PODSUMOWANIE ──────────────────────────────────────────────────
    result = {
        "task": task,
        "goal": task_plan.get("goal"),
        "work_dir": str(work_dir),
        "files_created": list(code_files.keys()),
        "tests_passed": tests_ok if "tests_ok" in dir() else False,
        "approved": review_result["approved"],
        "rounds": round_num,
        "issues": review_result["issues"],
        "started": started,
        "finished": datetime.now().isoformat(),
    }

    log("", "")
    log("══ WYNIK ══════════════════════════════", "")
    log(f"Status    : {'✓ SUKCES' if result['approved'] else '⚠ WYMAGA PRZEGLĄDU'}", "")
    log(f"Pliki     : {', '.join(result['files_created'])}", "")
    log(f"Katalog   : {work_dir}", "")
    log(f"Rundy     : {round_num}", "")

    # Zapis raportu
    report_path = work_dir / "multiagent_report.json"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(f"Raport    : {report_path}", "")

    return result


def main():
    parser = argparse.ArgumentParser(description="Multi-agent: Planner + Coder + Reviewer")
    parser.add_argument("task", help="Zadanie do wykonania")
    parser.add_argument("--work-dir", default="", help="Katalog roboczy")
    parser.add_argument("--max-rounds", type=int, default=2,
                        help="Max rund (kod→review→poprawki)")
    args = parser.parse_args()

    work_dir = Path(args.work_dir) if args.work_dir else (
        Path.home() / "qwen-agent" / "multiagent" / "workspace" /
        datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    result = orchestrate(args.task, work_dir, args.max_rounds)
    sys.exit(0 if result["approved"] else 1)


if __name__ == "__main__":
    main()
