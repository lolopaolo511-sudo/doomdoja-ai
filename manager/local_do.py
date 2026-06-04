#!/usr/bin/env python3
"""
local-do — wysyła zadanie do kolejki managera i czeka na wynik.

Użycie:
  local-do "napisz funkcję Python do parsowania CSV"
  local-do "zadanie" --local          # wymuś lokalny model
  local-do "zadanie" --auto           # router decyduje (domyślnie)
  local-do "zadanie" --budget 1024    # limit tokenów
  local-do "zadanie" --async          # nie czekaj na wynik
  local-do "zadanie" --priority 8     # wyższy priorytet (1-10)
  local-do --status                   # status kolejki i daemona
  local-do --result TASK_ID           # pobierz wynik po ID
  local-do --list                     # wylistuj oczekujące i gotowe

Pliki zadań wrzucane do: ~/qwen-agent/manager/inbox/
Wyniki w:               ~/qwen-agent/manager/outbox/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

MANAGER_DIR = Path(__file__).parent
INBOX_DIR = MANAGER_DIR / "inbox"
OUTBOX_DIR = MANAGER_DIR / "outbox"
FAILED_DIR = MANAGER_DIR / "failed"
PROCESSING_DIR = MANAGER_DIR / "processing"
PID_FILE = MANAGER_DIR / "daemon.pid"

DEFAULT_WAIT_S = 300    # max czas czekania na wynik
POLL_INTERVAL_S = 1.0   # jak często sprawdzamy outbox


# ── KOLORY TERMINALA ──────────────────────────────────────────────────────────

class C:
    RESET = "\033[0m"
    BOLD  = "\033[1m"
    GREEN = "\033[32m"
    BLUE  = "\033[34m"
    CYAN  = "\033[36m"
    YELLOW = "\033[33m"
    RED   = "\033[31m"
    GRAY  = "\033[90m"

def _colored(text: str, *codes: str) -> str:
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + C.RESET


# ── POMOCNICZE ────────────────────────────────────────────────────────────────

def _is_daemon_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, FileNotFoundError):
        return False


def _submit_task(task: str, mode: str, max_tokens: int | None, priority: int) -> str:
    task_id = f"ldо_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    payload = {
        "id": task_id,
        "task": task,
        "mode": mode,
        "priority": priority,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    task_file = INBOX_DIR / f"{task_id}.json"
    task_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return task_id


def _wait_for_result(task_id: str, timeout: float = DEFAULT_WAIT_S) -> dict | None:
    out_path = OUTBOX_DIR / f"{task_id}.json"
    fail_path = FAILED_DIR / f"{task_id}.json"
    fail_err_path = FAILED_DIR / f"{task_id}.error.json"

    deadline = time.monotonic() + timeout
    dots = 0
    while time.monotonic() < deadline:
        if out_path.exists():
            return json.loads(out_path.read_text(encoding="utf-8"))
        if fail_path.exists() or fail_err_path.exists():
            err_file = fail_err_path if fail_err_path.exists() else fail_path
            return json.loads(err_file.read_text(encoding="utf-8"))
        if sys.stdout.isatty():
            print(f"\r{_colored('Czekam na wynik', C.GRAY)} {'.' * (dots % 4 + 1):<4}", end="", flush=True)
        dots += 1
        time.sleep(POLL_INTERVAL_S)

    if sys.stdout.isatty():
        print()
    return None  # timeout


def _print_result(result: dict):
    if sys.stdout.isatty():
        print()  # newline po kropkach

    status  = result.get("status", "?")
    level   = result.get("level", "?")
    model   = result.get("model_used", "?")
    backend = result.get("backend", "?")
    tokens  = result.get("tokens_estimated", "?")
    duration = result.get("duration_s", "?")
    rounds  = result.get("rounds", "?")
    verifier = result.get("verifier_passed", False)
    esc_reason = result.get("escalation_reason")
    signals = result.get("level_signals", [])
    output  = result.get("output") or result.get("error") or "(brak wyniku)"

    level_icons = {"EASY": _colored("🟢 EASY", C.GREEN), "MEDIUM": _colored("🟡 MEDIUM", C.YELLOW),
                   "HARD": _colored("🔴 HARD", C.RED), "?": "?"}
    status_icon = {
        "done": _colored("✓", C.GREEN, C.BOLD),
        "needs_escalation": _colored("⬆", C.YELLOW, C.BOLD),
        "failed": _colored("✗", C.RED, C.BOLD),
    }.get(status, "?")

    backend_icon = "🏠" if backend == "local" else ("☁️ " if backend == "cloud" else "–")
    verifier_icon = _colored("✓", C.GREEN) if verifier else _colored("✗", C.YELLOW)

    print(f"\n{status_icon} {_colored('STATUS', C.BOLD)}: {status.upper()}")
    print(f"   🏷  poziom:   {level_icons.get(level, level)}", end="")
    if signals:
        print(f"  {_colored('(' + ', '.join(signals[:3]) + ')', C.GRAY)}", end="")
    print()
    print(f"   {backend_icon} model:    {_colored(model, C.CYAN)}")
    print(f"   ⏱  czas:     {duration}s")
    print(f"   📊 tokeny~:  {tokens}   rundy: {rounds}")
    print(f"   🔍 verifier: {verifier_icon}")

    if status == "needs_escalation":
        print(f"\n   {_colored('⬆  Wymaga eskalacji do cloud:', C.YELLOW, C.BOLD)}")
        print(f"   {_colored(esc_reason or '(brak szczegółów)', C.YELLOW)}")
        print(f"\n   {_colored('Jak uruchomić ręcznie w Claude/cloud:', C.GRAY)}")
        print(f"   {_colored('  Skopiuj zadanie z task_preview i wyślij bezpośrednio do Claude Desktop', C.GRAY)}")
    else:
        print(f"\n{_colored('─' * 60, C.GRAY)}")
        print(output)
        print(_colored("─" * 60, C.GRAY))

    if esc_reason and status != "needs_escalation":
        print(f"\n   {_colored('ℹ  Eskalowano:', C.CYAN)} {esc_reason}")


# ── KOMENDY ───────────────────────────────────────────────────────────────────

def cmd_submit(args):
    if not _is_daemon_running():
        print(_colored(
            "⚠  Daemon nie działa! Uruchom: python3 ~/qwen-agent/manager/daemon.py --start",
            C.YELLOW
        ))
        sys.exit(1)

    mode = "local" if args.local else "auto"
    task_id = _submit_task(args.task, mode=mode, max_tokens=args.budget, priority=args.priority)

    print(f"{_colored('→', C.BLUE, C.BOLD)} Zadanie wrzucone do kolejki")
    print(f"  ID:   {_colored(task_id, C.CYAN)}")
    print(f"  tryb: {mode} | priorytet: {args.priority}")
    if args.budget:
        print(f"  budget: {args.budget} tokenów")

    if args.async_:
        print(f"\n{_colored('(tryb async — nie czekam na wynik)', C.GRAY)}")
        print(f"Sprawdź wynik: local-do --result {task_id}")
        return

    result = _wait_for_result(task_id, timeout=DEFAULT_WAIT_S)
    if result is None:
        print(_colored(f"\nTimeout ({DEFAULT_WAIT_S}s) — wynik jeszcze nie gotowy.", C.YELLOW))
        print(f"Sprawdź później: local-do --result {task_id}")
        sys.exit(2)

    _print_result(result)


def cmd_result(task_id: str):
    out = OUTBOX_DIR / f"{task_id}.json"
    fail = FAILED_DIR / f"{task_id}.error.json"

    if out.exists():
        _print_result(json.loads(out.read_text(encoding="utf-8")))
    elif fail.exists():
        _print_result(json.loads(fail.read_text(encoding="utf-8")))
    else:
        # Sprawdź czy w processing
        proc = list(PROCESSING_DIR.glob(f"{task_id}*"))
        inbox = list(INBOX_DIR.glob(f"{task_id}*"))
        if proc:
            print(f"{_colored('⏳', C.YELLOW)} Zadanie {task_id} jest w toku (processing)")
        elif inbox:
            print(f"{_colored('📥', C.BLUE)} Zadanie {task_id} oczekuje w kolejce (inbox)")
        else:
            print(_colored(f"Nie znaleziono wyników dla ID: {task_id}", C.RED))
            sys.exit(1)


def cmd_status():
    daemon_ok = _is_daemon_running()
    daemon_txt = _colored("DZIAŁA", C.GREEN, C.BOLD) if daemon_ok else _colored("ZATRZYMANY", C.RED, C.BOLD)
    print(f"\n{_colored('Manager Daemon:', C.BOLD)} {daemon_txt}")

    if daemon_ok and PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        print(f"  PID: {pid}")

    inbox = list(INBOX_DIR.glob("*.json")) + list(INBOX_DIR.glob("*.yaml"))
    proc = list(PROCESSING_DIR.glob("*.json")) + list(PROCESSING_DIR.glob("*.yaml"))
    outbox = list(OUTBOX_DIR.glob("*.json"))
    failed = [f for f in FAILED_DIR.glob("*.json") if not f.name.endswith(".error.json")]

    print(f"\n{_colored('Kolejka:', C.BOLD)}")
    print(f"  📥 inbox:      {len(inbox)}")
    print(f"  ⚙️  processing: {len(proc)}")
    print(f"  ✅ outbox:     {len(outbox)}")
    print(f"  ❌ failed:     {len(failed)}")
    print()


def cmd_list():
    print(f"\n{_colored('Ostatnie zadania', C.BOLD, C.CYAN)}:")

    results = sorted(OUTBOX_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
    if not results:
        print("  (brak gotowych wyników)")
    else:
        for r in results:
            try:
                d = json.loads(r.read_text(encoding="utf-8"))
                icon = "✅" if d.get("status") == "done" else "❌"
                model = d.get("model_used", "?")
                duration = d.get("duration_s", "?")
                preview = (d.get("task_preview") or "")[:60]
                print(f"  {icon} {_colored(d['id'], C.CYAN)}  [{model}, {duration}s]  {preview}")
            except Exception:
                print(f"  ? {r.name}")

    failures = sorted(FAILED_DIR.glob("*.error.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    if failures:
        print(f"\n{_colored('Ostatnie błędy:', C.RED)}:")
        for f in failures:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                print(f"  ❌ {f.stem}  {d.get('error', '?')[:80]}")
            except Exception:
                print(f"  ❌ {f.name}")
    print()


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="local-do",
        description="Wrzuć zadanie do kolejki managera i pobierz wynik od lokalnego agenta.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Przykłady:
  local-do "napisz test pytest dla funkcji licz_vat"
  local-do "zrób prosty CRUD w SQLite" --local --budget 2048
  local-do "przeanalizuj architekturę microservices" --auto
  local-do "moje zadanie" --async
  local-do --status
  local-do --list""",
    )
    parser.add_argument("task", nargs="?", help="Treść zadania")
    parser.add_argument("--local", action="store_true", help="Wymuś lokalny model (Ollama)")
    parser.add_argument("--auto", action="store_true", help="Router decyduje local/cloud (domyślnie)")
    parser.add_argument("--budget", "-b", type=int, metavar="N", help="Limit max tokenów")
    parser.add_argument("--priority", "-p", type=int, default=5, metavar="1-10", help="Priorytet (1=min, 10=max)")
    parser.add_argument("--async", dest="async_", action="store_true", help="Nie czekaj na wynik")
    parser.add_argument("--status", "-s", action="store_true", help="Pokaż status daemona i kolejki")
    parser.add_argument("--list", "-l", action="store_true", help="Listuj ostatnie zadania")
    parser.add_argument("--result", "-r", metavar="TASK_ID", help="Pobierz wynik po ID")

    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.list:
        cmd_list()
    elif args.result:
        cmd_result(args.result)
    elif args.task:
        cmd_submit(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
