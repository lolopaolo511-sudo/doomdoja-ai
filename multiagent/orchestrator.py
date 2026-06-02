#!/usr/bin/env python3
"""
Orkiestrator multi-agenta v2: Planner → Coder → Verifier → (poprawki) → DONE

Nowe flagi:
  --verify      Uruchom twardy Verifier po implementacji (domyślnie: ON)
  --no-verify   Wyłącz Verifier (kompatybilność wsteczna)
  --resume      Wznów przerwaną sesję z work_dir/plan_state.json
  --max-verify-rounds N  Max rund poprawek verifier (domyślnie: 3)

Użycie:
  python3 orchestrator.py "zadanie" [--work-dir /tmp/projekt]
  python3 orchestrator.py "zadanie" --profile 01-lead-generation [--plan-only]
  python3 orchestrator.py "zadanie" --verify --max-verify-rounds 3
  python3 orchestrator.py "zadanie" --no-verify  # v1 behavior
  python3 orchestrator.py "zadanie" --resume --work-dir /tmp/prev_run
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def _import_llm_modules():
    global plan, plan_resumed, save_state, implement_all_steps, review, run_tests
    from planner import plan, plan_resumed, save_state
    from coder import implement_all_steps
    from reviewer import review, run_tests

PROMPT_LIBRARY_DIR = Path(__file__).parent.parent / "prompt-library"


def log(msg: str, role: str = ""):
    prefix = f"[{role.upper():8}]" if role else "[        ]"
    print(f"{prefix} {msg}")


# ── PROFIL ────────────────────────────────────────────────────────────────────

class Profile:
    def __init__(self, name: str):
        self.name = name
        self.dir = self._resolve_dir(name)
        self.meta = self._load_yaml()
        self.system = self._read("system.md")
        self.planner_prompt = self._read("planner.md")
        self.coder_prompt = self._read("coder.md")
        self.reviewer_prompt = self._read("reviewer.md")

    def _resolve_dir(self, name: str) -> Path:
        if (PROMPT_LIBRARY_DIR / name).is_dir():
            return PROMPT_LIBRARY_DIR / name
        for d in sorted(PROMPT_LIBRARY_DIR.iterdir()):
            if d.is_dir() and (d.name == name or d.name.endswith(f"-{name}")):
                return d
        available = [d.name for d in sorted(PROMPT_LIBRARY_DIR.iterdir()) if d.is_dir()]
        raise FileNotFoundError(
            f"Profil '{name}' nie znaleziony w {PROMPT_LIBRARY_DIR}.\n"
            f"Dostępne: {', '.join(available)}"
        )

    def _read(self, filename: str) -> str:
        p = self.dir / filename
        return p.read_text(encoding="utf-8").strip() if p.exists() else ""

    def _load_yaml(self) -> dict:
        p = self.dir / "profile.yaml"
        if not p.exists():
            return {}
        try:
            import yaml
            return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except ImportError:
            result: dict = {}
            for line in p.read_text(encoding="utf-8").splitlines():
                if ":" in line and not line.startswith(" ") and not line.startswith("#"):
                    key, _, val = line.partition(":")
                    val = val.strip()
                    if val:
                        result[key.strip()] = val
            return result

    def models(self) -> dict:
        return self.meta.get("models", {})

    def describe(self):
        log(f"Profil     : {self.name}", "profile")
        log(f"Ścieżka    : {self.dir}", "profile")
        log(f"Opis       : {self.meta.get('description', '—')}", "profile")
        models = self.models()
        if models:
            log(f"Modele     : planner={models.get('planner','?')} "
                f"coder={models.get('coder','?')} "
                f"reviewer={models.get('reviewer','?')}", "profile")


def load_profile(name: str) -> Profile:
    return Profile(name)


# ── PLAN-ONLY ─────────────────────────────────────────────────────────────────

def plan_only(task: str, profile: "Profile | None", work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    log("=== TRYB PLAN-ONLY (dry-run) ===", "")
    if profile:
        profile.describe()
        for attr in ("system", "planner_prompt", "coder_prompt", "reviewer_prompt"):
            label = attr.replace("_prompt", "").replace("_", " ")
            content = getattr(profile, attr)
            if content:
                log(f"── {label}.md ──────────────────────", "")
                for line in content.splitlines()[:4]:
                    log(f"  {line}", "")

    log(f"Zadanie    : {task}", "")
    log("Prompty załadowane pomyślnie.", "")
    log("UWAGA: realne uruchomienie wymaga Ollamy + kluczy Airtable/Make.com.", "")

    result = {
        "task": task,
        "profile": profile.name if profile else None,
        "plan_only": True,
        "status": "dry-run OK",
        "timestamp": datetime.now().isoformat(),
    }
    (work_dir / "plan_only_report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    log(f"Raport     : {work_dir / 'plan_only_report.json'}", "")
    return result


# ── GŁÓWNA ORKIESTRACJA ───────────────────────────────────────────────────────

def orchestrate(
    task: str,
    work_dir: Path,
    max_rounds: int = 2,
    profile: "Profile | None" = None,
    verify: bool = True,
    max_verify_rounds: int = 3,
    resume: bool = False,
) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now().isoformat()

    if profile:
        profile.describe()
        log("", "")

    # Nadpisz system prompty w modułach jeśli profil je dostarcza
    if profile:
        import planner as planner_mod
        import coder as coder_mod
        import reviewer as reviewer_mod
        if profile.system:
            planner_mod.SYSTEM_PROMPT = profile.system + "\n\n" + planner_mod.SYSTEM_PROMPT
            coder_mod.SYSTEM_PROMPT = profile.system + "\n\n" + coder_mod.SYSTEM_PROMPT
            reviewer_mod.SYSTEM_PROMPT = profile.system + "\n\n" + reviewer_mod.SYSTEM_PROMPT
        if profile.planner_prompt:
            planner_mod.SYSTEM_PROMPT = profile.planner_prompt + "\n\n" + planner_mod.SYSTEM_PROMPT
        if profile.coder_prompt:
            coder_mod.SYSTEM_PROMPT = profile.coder_prompt + "\n\n" + coder_mod.SYSTEM_PROMPT
        if profile.reviewer_prompt:
            reviewer_mod.SYSTEM_PROMPT = profile.reviewer_prompt + "\n\n" + reviewer_mod.SYSTEM_PROMPT

    # ── ROLA 1: PLANNER ──────────────────────────────────────────────────────
    if resume:
        log(f"Tryb wznowienia — szukam stanu w: {work_dir}", "planner")
        task_plan, completed_ids = plan_resumed(task, work_dir)
    else:
        log(f"Analizuję zadanie: {task[:80]}", "planner")
        task_plan = plan(task)
        completed_ids = []
        save_state(task_plan, work_dir, completed_ids)

    log(f"Cel: {task_plan.get('goal', '?')}", "planner")
    log(f"Kroków: {len(task_plan.get('steps', []))} (ukończonych wcześniej: {len(completed_ids)})", "planner")

    for s in task_plan.get("steps", []):
        done_mark = " ✓" if s["id"] in completed_ids else ""
        log(f"  {s['id']}. {s['title']} → {s.get('file', '?')}{done_mark}", "planner")
        for criterion in s.get("acceptance_criteria", [])[:2]:
            log(f"     ✓ {criterion}", "planner")

    # ── ROLA 2: CODER (z pętlą code-review) ─────────────────────────────────
    code_files: dict[str, str] = {}
    review_result: dict = {"approved": False, "issues": [], "fixes": ""}

    for round_num in range(1, max_rounds + 1):
        log(f"Runda implementacji {round_num}/{max_rounds}", "coder")

        if round_num > 1 and review_result.get("fixes"):
            log("Implementuję poprawki z code review", "coder")
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
            # Pomiń już ukończone kroki przy wznowieniu
            if completed_ids:
                from planner import plan as _plan_module
                remaining_plan = dict(task_plan)
                remaining_plan["steps"] = [
                    s for s in task_plan.get("steps", [])
                    if s["id"] not in completed_ids
                ]
                new_files = implement_all_steps(remaining_plan, work_dir)
            else:
                new_files = implement_all_steps(task_plan, work_dir)
            code_files.update(new_files)

        # Aktualizuj stan po implementacji
        all_ids = [s["id"] for s in task_plan.get("steps", [])]
        save_state(task_plan, work_dir, all_ids)

        # ── ROLA 3: REVIEWER (LLM code review) ──────────────────────────────
        log("Uruchamiam testy pytest...", "reviewer")
        tests_ok, test_output = run_tests(work_dir)
        log(f"Testy: {'PASS ✓' if tests_ok else 'FAIL ✗'}", "reviewer")
        if test_output:
            for line in test_output.splitlines()[-6:]:
                log(f"  {line}", "reviewer")

        log("Przeglądam kod (LLM review)...", "reviewer")
        review_result = review(task_plan, code_files, test_output)

        if review_result["approved"] and tests_ok:
            log("LLM APPROVED ✓", "reviewer")
            break
        else:
            if review_result["issues"]:
                log(f"Znalezione problemy ({len(review_result['issues'])}):", "reviewer")
                for issue in review_result["issues"][:4]:
                    log(f"  {issue}", "reviewer")
            if round_num < max_rounds:
                log("Zlecam poprawki coderowi...", "reviewer")

    # ── ROLA 4: VERIFIER (twarda weryfikacja artefaktów) ─────────────────────
    verifier_passed = True
    verifier_report = "(pominięto — --no-verify)"
    verifier_rounds_used = 0

    if verify:
        from verifier import Verifier
        v = Verifier(max_fix_rounds=max_verify_rounds)

        for vround in range(1, max_verify_rounds + 1):
            verifier_rounds_used = vround
            log(f"Weryfikacja artefaktów (runda {vround}/{max_verify_rounds})...", "verifier")

            verifier_passed, verifier_report = v.verify_and_report(work_dir)

            log(verifier_report, "verifier")

            if verifier_passed:
                log("VERIFIER ✓ — wszystkie artefakty poprawne", "verifier")
                break
            else:
                log(f"VERIFIER ✗ — znalezione problemy", "verifier")

                if vround < max_verify_rounds:
                    # Zbierz wskazówki i przekaż do codera
                    fix_hints = v.collect_fix_hints(work_dir)
                    if fix_hints:
                        log(f"Przekazuję wskazówki naprawcze do codera...", "verifier")
                        fix_step = {
                            "id": 100 + vround,
                            "title": f"Naprawki verifier (runda {vround})",
                            "description": fix_hints,
                            "file": list(code_files.keys())[0] if code_files else "main.py",
                        }
                        from coder import implement_step, write_code
                        for fname, code in list(code_files.items()):
                            fixed = implement_step(fix_step, code)
                            fpath = work_dir / fname
                            write_code(fpath, fixed)
                            code_files[fname] = fixed
                    else:
                        log("Brak wskazówek naprawczych — przerywam pętlę verifier", "verifier")
                        break
                else:
                    log(
                        f"VERIFIER: wyczerpano {max_verify_rounds} rund poprawek — "
                        "artefakt nadal niekompletny. Uczciwy raport błędów poniżej.",
                        "verifier"
                    )

    # ── PODSUMOWANIE ──────────────────────────────────────────────────────────
    overall_ok = review_result["approved"] and verifier_passed
    result = {
        "task": task,
        "profile": profile.name if profile else None,
        "goal": task_plan.get("goal"),
        "work_dir": str(work_dir),
        "files_created": list(code_files.keys()),
        "tests_passed": tests_ok if "tests_ok" in dir() else False,
        "llm_approved": review_result["approved"],
        "verifier_passed": verifier_passed,
        "verifier_report": verifier_report,
        "verifier_rounds": verifier_rounds_used,
        "overall_approved": overall_ok,
        "rounds": round_num if "round_num" in dir() else 0,
        "issues": review_result["issues"],
        "started": started,
        "finished": datetime.now().isoformat(),
    }

    log("", "")
    log("══ WYNIK ══════════════════════════════", "")
    log(f"Status LLM : {'✓ APPROVED' if result['llm_approved'] else '⚠ NEEDS FIXES'}", "")
    log(f"Verifier   : {'✓ PASS' if result['verifier_passed'] else '✗ FAIL'}", "")
    log(f"OVERALL    : {'✓ SUKCES' if overall_ok else '✗ NIEKOMPLETNE'}", "")
    log(f"Pliki      : {', '.join(result['files_created'])}", "")
    log(f"Katalog    : {work_dir}", "")

    report_path = work_dir / "multiagent_report.json"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(f"Raport     : {report_path}", "")

    return result


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Multi-agent v2: Planner + Coder + Verifier")
    parser.add_argument("task", help="Zadanie do wykonania")
    parser.add_argument("--work-dir", default="", help="Katalog roboczy")
    parser.add_argument("--max-rounds", type=int, default=2,
                        help="Max rund code→review (domyślnie: 2)")
    parser.add_argument("--profile", default="",
                        help="Profil projektu z prompt-library/")
    parser.add_argument("--plan-only", action="store_true",
                        help="Dry-run: tylko załaduj profil bez LLM")
    parser.add_argument("--verify", action="store_true", default=True,
                        help="Uruchom twardy Verifier po implementacji (domyślnie: ON)")
    parser.add_argument("--no-verify", action="store_true", default=False,
                        help="Wyłącz Verifier (kompatybilność z v1)")
    parser.add_argument("--max-verify-rounds", type=int, default=3,
                        help="Max rund poprawek verifier (domyślnie: 3)")
    parser.add_argument("--resume", action="store_true",
                        help="Wznów przerwane zadanie z --work-dir/plan_state.json")
    args = parser.parse_args()

    # --no-verify wyłącza weryfikację
    verify_enabled = args.verify and not args.no_verify

    profile = None
    if args.profile:
        try:
            profile = load_profile(args.profile)
        except FileNotFoundError as e:
            print(f"[ERROR   ] {e}", file=sys.stderr)
            sys.exit(1)

    work_dir = Path(args.work_dir) if args.work_dir else (
        Path.home() / "qwen-agent" / "multiagent" / "workspace" /
        datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    if args.plan_only:
        plan_only(args.task, profile, work_dir)
        sys.exit(0)

    _import_llm_modules()
    result = orchestrate(
        args.task, work_dir,
        max_rounds=args.max_rounds,
        profile=profile,
        verify=verify_enabled,
        max_verify_rounds=args.max_verify_rounds,
        resume=args.resume,
    )
    sys.exit(0 if result["overall_approved"] else 1)


if __name__ == "__main__":
    main()
