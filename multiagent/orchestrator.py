#!/usr/bin/env python3
"""
Orkiestrator multi-agenta: Planner → Coder → Reviewer → (poprawki) → DONE
Użycie: python3 orchestrator.py "zadanie" [--work-dir /tmp/projekt] [--max-rounds 2]
        python3 orchestrator.py "zadanie" --profile 01-lead-generation [--plan-only]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Dodaj katalog multi-agenta do path
sys.path.insert(0, str(Path(__file__).parent))

# Moduły LLM ładowane leniwie — nie są potrzebne w trybie --plan-only
def _import_llm_modules():
    global plan, implement_all_steps, review, run_tests
    from planner import plan
    from coder import implement_all_steps
    from reviewer import review, run_tests

PROMPT_LIBRARY_DIR = Path(__file__).parent.parent / "prompt-library"


def log(msg: str, role: str = ""):
    prefix = f"[{role.upper():8}]" if role else "[        ]"
    print(f"{prefix} {msg}")


# ── ŁADOWANIE PROFILU ────────────────────────────────────────────────────────

class Profile:
    """Profil projektu załadowany z prompt-library/<name>/."""

    def __init__(self, name: str):
        self.name = name
        self.dir = self._resolve_dir(name)
        self.meta = self._load_yaml()
        self.system = self._read("system.md")
        self.planner_prompt = self._read("planner.md")
        self.coder_prompt = self._read("coder.md")
        self.reviewer_prompt = self._read("reviewer.md")

    def _resolve_dir(self, name: str) -> Path:
        # Szukaj po dokładnej nazwie folderu lub prefiksie (np. "01-lead-generation" lub "lead-generation")
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
            # Minimalny parser bez pyyaml — wyciąga klucze: wartość z płaskiego YAML
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
        tools = self.meta.get("tools", [])
        if tools:
            log(f"Narzędzia  : {', '.join(tools)}", "profile")


def load_profile(name: str) -> Profile:
    return Profile(name)


# ── PLAN-ONLY (dry-run) ──────────────────────────────────────────────────────

def plan_only(task: str, profile: Profile | None, work_dir: Path) -> dict:
    """Dry-run — tylko planowanie, bez wywoływania LLM ani zapisywania kodu."""
    work_dir.mkdir(parents=True, exist_ok=True)

    log("=== TRYB PLAN-ONLY (dry-run) ===", "")
    if profile:
        profile.describe()
        log("", "")
        log("── system.md ──────────────────────────────────────────", "")
        for line in profile.system.splitlines()[:6]:
            log(f"  {line}", "")
        log("", "")
        log("── planner.md ─────────────────────────────────────────", "")
        for line in profile.planner_prompt.splitlines()[:6]:
            log(f"  {line}", "")
        log("", "")
        log("── coder.md ───────────────────────────────────────────", "")
        for line in profile.coder_prompt.splitlines()[:4]:
            log(f"  {line}", "")
        log("", "")
        log("── reviewer.md ────────────────────────────────────────", "")
        for line in profile.reviewer_prompt.splitlines()[:4]:
            log(f"  {line}", "")
        log("", "")

    log(f"Zadanie    : {task}", "")
    log("Prompty załadowane pomyślnie.", "")
    log("UWAGA: realne uruchomienie wymaga Ollamy + kluczy Airtable/Make.com.", "")

    result = {
        "task": task,
        "profile": profile.name if profile else None,
        "plan_only": True,
        "prompts_loaded": {
            "system": bool(profile and profile.system),
            "planner": bool(profile and profile.planner_prompt),
            "coder": bool(profile and profile.coder_prompt),
            "reviewer": bool(profile and profile.reviewer_prompt),
        },
        "status": "dry-run OK",
        "timestamp": datetime.now().isoformat(),
    }

    report_path = work_dir / "plan_only_report.json"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(f"Raport     : {report_path}", "")
    return result


# ── GŁÓWNA ORKIESTRACJA ──────────────────────────────────────────────────────

def orchestrate(task: str, work_dir: Path, max_rounds: int = 2,
                profile: "Profile | None" = None) -> dict:
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
        "profile": profile.name if profile else None,
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
    parser.add_argument("--profile", default="",
                        help="Profil projektu z prompt-library/ (np. 01-lead-generation)")
    parser.add_argument("--plan-only", action="store_true",
                        help="Dry-run: załaduj profil i wyświetl prompty bez wywoływania LLM")
    args = parser.parse_args()

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
    result = orchestrate(args.task, work_dir, args.max_rounds, profile)
    sys.exit(0 if result["approved"] else 1)


if __name__ == "__main__":
    main()
