#!/usr/bin/env python3
"""
Manager Daemon — obserwuje inbox/, przetwarza zadania przez lokalnego agenta.

Tryby (pole mode w zadaniu):
  local  — wymusza model Ollama, bez routera
  auto   — HybridRouter decyduje local/cloud

Polityka 3 poziomów (auto-wykrywana przez LevelClassifier):
  EASY   → lokalny model, bez eskalacji, verifier opcjonalny
  MEDIUM → lokalny NAJPIERW; verifier sprawdza; po N failach → cloud
  HARD   → od razu needs_escalation w outbox (bez marnowania rund)

Format pliku zadania (JSON lub YAML w inbox/):
  {
    "id": "task_001",
    "task": "napisz funkcję Python ...",
    "mode": "local",     // local | auto
    "max_tokens": 2048,  // opcjonalne
    "priority": 5        // 1-10, wyższy = ważniejszy (opcjonalne)
  }

Format wyniku w outbox/<id>.json:
  {
    "id": "task_001",
    "status": "done" | "needs_escalation",
    "level": "EASY" | "MEDIUM" | "HARD",
    "output": "...",
    "model_used": "deepseek-coder-v2:16b",
    "backend": "local" | "cloud",
    "tokens_estimated": 150,
    "duration_s": 3.2,
    "verifier_passed": true,
    "rounds": 1,
    "escalation_reason": null | "...",
    "error": null
  }

Uruchomienie:
  python3 daemon.py --start       # uruchom (foreground lub przez launchd)
  python3 daemon.py --status      # sprawdź czy działa
  python3 daemon.py --stop        # zatrzymaj przez PID file
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── ŚCIEŻKI ───────────────────────────────────────────────────────────────────

MANAGER_DIR = Path(__file__).parent
INBOX_DIR = MANAGER_DIR / "inbox"
PROCESSING_DIR = MANAGER_DIR / "processing"
OUTBOX_DIR = MANAGER_DIR / "outbox"
FAILED_DIR = MANAGER_DIR / "failed"
LOGS_DIR = MANAGER_DIR / "logs"
PID_FILE = MANAGER_DIR / "daemon.pid"
LOG_FILE = LOGS_DIR / f"daemon_{datetime.now().strftime('%Y%m%d')}.log"

# Dodaj root projektu do path
_ROOT = str(MANAGER_DIR.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

POLL_INTERVAL_S = 2.0

# Ile failów verifier przed eskalacją dla MEDIUM (override: pole medium_escalate_after w zadaniu)
MEDIUM_ESCALATE_AFTER = 2
# Co ile zadań uruchamiamy kalibrację (0 = wyłączona)
CALIBRATION_EVERY_N = 20

# ── LOGGING ───────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    fmt = "%(asctime)s [%(levelname)-7s] %(message)s"
    handlers: list[logging.Handler] = [
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    return logging.getLogger("manager.daemon")


logger = logging.getLogger("manager.daemon")


# ── PARSER ZADANIA ────────────────────────────────────────────────────────────

def load_task(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
            return yaml.safe_load(text) or {}
        except ImportError:
            # Prosta heurystyka: przekonwertuj YAML na JSON
            data: dict = {}
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    k, _, v = line.partition(":")
                    v = v.strip().strip('"').strip("'")
                    try:
                        data[k.strip()] = int(v)
                    except ValueError:
                        try:
                            data[k.strip()] = float(v)
                        except ValueError:
                            data[k.strip()] = v
            return data
    else:
        return json.loads(text)


def validate_task(data: dict) -> tuple[bool, str]:
    if not data.get("task"):
        return False, "brak pola 'task'"
    if not data.get("id"):
        return False, "brak pola 'id'"
    mode = data.get("mode", "auto")
    if mode not in ("local", "auto"):
        return False, f"nieznany tryb: {mode!r} (dozwolone: local, auto)"
    return True, ""


# ── PRZETWARZANIE ZADANIA — 3-POZIOMOWA POLITYKA ────────────────────────────

def process_task(data: dict) -> dict:
    """
    Przetwarza jedno zadanie zgodnie z 3-poziomową polityką:
      EASY   → lokalny model, bez eskalacji
      MEDIUM → lokalny NAJPIERW; verifier; po N failach → cloud
      HARD   → od razu needs_escalation (bez prób lokalnie)
    """
    task_id   = data["id"]
    task_text = data["task"]
    mode      = data.get("mode", "auto")
    max_tokens: Optional[int] = data.get("max_tokens")
    priority  = data.get("priority", 5)
    escalate_after = data.get("medium_escalate_after", MEDIUM_ESCALATE_AFTER)

    # ── Klasyfikacja poziomu ──────────────────────────────────────────────────
    from manager.level import classify_level
    level_result = classify_level(task_text)
    level = level_result.level

    # Tryb "local" zawsze wymusza EASY (niezależnie od klasyfikacji)
    if mode == "local":
        level = "EASY"

    logger.info(
        f"[{task_id}] START level={level} mode={mode} "
        f"priority={priority} score={level_result.score} "
        f"signals={level_result.signals[:3]}"
    )

    t0 = time.monotonic()

    # ── HARD → od razu needs_escalation ──────────────────────────────────────
    if level == "HARD":
        duration = time.monotonic() - t0
        reason = f"HARD: {level_result.reason} | sygnały: {', '.join(level_result.signals[:4])}"
        logger.info(f"[{task_id}] HARD → needs_escalation  {reason}")
        _record_feedback(task_id, task_text, "HARD", "none", "none",
                         False, 0, duration, escalated=True)
        return {
            "id": task_id,
            "status": "needs_escalation",
            "level": "HARD",
            "output": "",
            "model_used": "none",
            "backend": "none",
            "tokens_estimated": 0,
            "duration_s": round(duration, 3),
            "rounds": 0,
            "verifier_passed": False,
            "escalation_reason": reason,
            "error": None,
            "completed_at": datetime.now().isoformat(),
            "task_preview": task_text[:120],
        }

    # ── EASY / MEDIUM → próba lokalna ─────────────────────────────────────────
    local_model = _get_local_model()
    backend_name = "local"
    model_used   = local_model
    output       = ""
    error_msg: Optional[str] = None
    verifier_passed = False
    rounds = 0
    escalated = False
    escalation_reason: Optional[str] = None

    max_local_rounds = 1 if level == "EASY" else escalate_after

    for round_num in range(1, max_local_rounds + 1):
        rounds = round_num
        try:
            from router.backends.local import LocalBackend
            output = LocalBackend().generate(task_text, max_tokens=max_tokens)
            error_msg = None
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.error(f"[{task_id}] runda {round_num} BŁĄD: {error_msg}")
            output = ""

        verifier_passed = bool(output and output.strip() and not error_msg)
        logger.info(
            f"[{task_id}] runda={round_num}/{max_local_rounds} "
            f"verifier={'✓' if verifier_passed else '✗'}"
        )

        if verifier_passed:
            break  # sukces — nie potrzeba kolejnych rund

    # ── MEDIUM: eskalacja po wyczerpaniu rund ─────────────────────────────────
    if level == "MEDIUM" and not verifier_passed:
        logger.info(f"[{task_id}] MEDIUM fail po {rounds} rundach → eskalacja cloud")
        escalated = True
        escalation_reason = f"local fail po {rounds} rundach verifier"

        try:
            from router import HybridRouter, RouterContext
            router = HybridRouter()
            ctx = RouterContext(
                step_title=task_text[:80],
                verifier_fails=rounds,
                force_cloud=True,
            )
            decision = router.choose_model(task_text, ctx)
            model_used   = decision.model
            backend_name = decision.backend
            logger.info(f"[{task_id}] Cloud router: {decision.summary()}")

            if decision.backend == "cloud":
                from router.backends.cloud import CloudBackend
                output = CloudBackend().generate(task_text, model=decision.model, max_tokens=max_tokens)
                error_msg = None
            else:
                # cloud niedostępny → local-only, zostań przy ostatnim outputcie
                logger.warning(f"[{task_id}] Cloud niedostępny, zostaję przy lokalnym wyniku")
                backend_name = "local"
                model_used   = local_model
                escalated    = False

            verifier_passed = bool(output and output.strip())
        except Exception as exc:
            error_msg = f"cloud error: {type(exc).__name__}: {exc}"
            logger.error(f"[{task_id}] Błąd eskalacji: {error_msg}")

    duration = time.monotonic() - t0
    _record_feedback(task_id, task_text, level, backend_name, model_used,
                     verifier_passed, rounds, duration, escalated=escalated,
                     error=error_msg)

    status = "done" if (verifier_passed and not error_msg) else "failed"
    result = {
        "id": task_id,
        "status": status,
        "level": level,
        "output": output,
        "model_used": model_used,
        "backend": backend_name,
        "tokens_estimated": len(output.split()) if output else 0,
        "duration_s": round(duration, 3),
        "rounds": rounds,
        "verifier_passed": verifier_passed,
        "escalation_reason": escalation_reason,
        "error": error_msg,
        "completed_at": datetime.now().isoformat(),
        "task_preview": task_text[:120],
        "level_score": level_result.score,
        "level_signals": level_result.signals,
    }

    icon = "✅" if status == "done" else "❌"
    logger.info(
        f"[{task_id}] {icon} {status.upper()} level={level} "
        f"backend={backend_name} model={model_used} "
        f"rounds={rounds} tokens~{result['tokens_estimated']} t={duration:.2f}s"
    )
    return result


def _record_feedback(
    task_id: str, task_text: str, level: str, backend: str, model: str,
    verifier_passed: bool, rounds: int, duration: float,
    escalated: bool = False, error: Optional[str] = None,
) -> None:
    """Zapisz wynik do memory2 (nieblokująco, ignoruj błędy)."""
    try:
        from manager.level_feedback import get_feedback
        get_feedback().record(
            task_id=task_id,
            task_preview=task_text[:80],
            level=level,
            backend=backend,
            model=model,
            verifier_passed=verifier_passed,
            rounds=rounds,
            duration_s=duration,
            escalated=escalated,
            error=error,
        )
    except Exception as e:
        logger.debug(f"[feedback] zapis pominięty: {e}")


def _get_local_model() -> str:
    """Odczytuje nazwę modelu lokalnego z konfiguracji routera."""
    try:
        import yaml
        cfg_path = MANAGER_DIR.parent / "router" / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        return cfg.get("local", {}).get("model", "deepseek-coder-v2:16b")
    except Exception:
        return "deepseek-coder-v2:16b"


# ── GŁÓWNA PĘTLA ──────────────────────────────────────────────────────────────

class ManagerDaemon:
    def __init__(self):
        self._running = False
        self._tasks_since_cal = 0

    def start(self):
        setup_logging()
        from manager.level import get_classifier
        clf = get_classifier()
        logger.info("=== Manager Daemon URUCHOMIONY ===")
        logger.info(f"  inbox:      {INBOX_DIR}")
        logger.info(f"  outbox:     {OUTBOX_DIR}")
        logger.info(f"  poll:       {POLL_INTERVAL_S}s")
        logger.info(f"  level thresholds: MEDIUM≥{clf.medium_threshold} HARD≥{clf.hard_threshold}")
        logger.info(f"  MEDIUM eskalacja po: {MEDIUM_ESCALATE_AFTER} rundach")

        self._write_pid()
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._running = True
        self._loop()

    def _loop(self):
        while self._running:
            self._scan_inbox()
            time.sleep(POLL_INTERVAL_S)
        logger.info("=== Manager Daemon ZATRZYMANY ===")
        PID_FILE.unlink(missing_ok=True)

    def _scan_inbox(self):
        candidates: list[Path] = sorted(
            list(INBOX_DIR.glob("*.json")) + list(INBOX_DIR.glob("*.yaml")) + list(INBOX_DIR.glob("*.yml")),
            key=lambda p: p.stat().st_mtime,
        )
        if candidates:
            # Sortuj według priorytetu (wysokość priority w nazwie lub domyślnie kolejność)
            candidates = _sort_by_priority(candidates)
            task_file = candidates[0]
            self._handle_task(task_file)

    def _handle_task(self, task_file: Path):
        # Przenieś do processing/
        proc_file = PROCESSING_DIR / task_file.name
        try:
            task_file.rename(proc_file)
        except FileNotFoundError:
            return  # Inny wątek/proces zabrał już plik

        try:
            data = load_task(proc_file)
        except Exception as exc:
            logger.error(f"Błąd parsowania {task_file.name}: {exc}")
            self._move_to_failed(proc_file, str(exc))
            return

        ok, reason = validate_task(data)
        if not ok:
            logger.error(f"Nieprawidłowe zadanie {task_file.name}: {reason}")
            self._move_to_failed(proc_file, reason)
            return

        result = process_task(data)

        # Zapis do outbox/ (done, needs_escalation) lub failed/
        task_id = data["id"]
        out_statuses = ("done", "needs_escalation")
        if result["status"] in out_statuses:
            out_path = OUTBOX_DIR / f"{task_id}.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"Wynik zapisany: {out_path} [{result['status']}]")
        else:
            self._move_to_failed(proc_file, result.get("error") or "unknown error", result)

        # Usuń plik z processing/
        proc_file.unlink(missing_ok=True)

        # Kalibracja co N zadań
        self._tasks_since_cal += 1
        if CALIBRATION_EVERY_N > 0 and self._tasks_since_cal >= CALIBRATION_EVERY_N:
            self._tasks_since_cal = 0
            self._run_calibration()

    def _move_to_failed(self, proc_file: Path, reason: str, result: Optional[dict] = None):
        fail_path = FAILED_DIR / proc_file.name
        proc_file.rename(fail_path)
        meta = FAILED_DIR / (proc_file.stem + ".error.json")
        meta.write_text(
            json.dumps({"error": reason, "result": result, "at": datetime.now().isoformat()},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.warning(f"Zadanie przeniesione do failed: {fail_path.name} — {reason}")

    def _run_calibration(self):
        try:
            from manager.level_calibration import run_calibration
            report = run_calibration()
            if report.changes:
                logger.info(f"[calibration] Progi zmienione: {report.changes}")
            else:
                logger.debug("[calibration] Brak zmian progów")
        except Exception as e:
            logger.debug(f"[calibration] pominięta: {e}")

    def _handle_signal(self, signum, frame):
        logger.info(f"Otrzymano sygnał {signum}, zatrzymuję daemon...")
        self._running = False

    def _write_pid(self):
        PID_FILE.write_text(str(os.getpid()))


def _sort_by_priority(files: list[Path]) -> list[Path]:
    def _get_priority(p: Path) -> int:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return -(data.get("priority", 5))  # wyższy priority = wcześniej
        except Exception:
            return 0
    try:
        return sorted(files, key=_get_priority)
    except Exception:
        return files


# ── KOMENDY CLI ───────────────────────────────────────────────────────────────

def cmd_start():
    daemon = ManagerDaemon()
    daemon.start()


def cmd_stop():
    if not PID_FILE.exists():
        print("Daemon nie działa (brak PID file)")
        return
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Wysłano SIGTERM do PID {pid}")
    except ProcessLookupError:
        print(f"Proces {pid} nie istnieje, usuwam PID file")
        PID_FILE.unlink(missing_ok=True)


def cmd_status():
    if not PID_FILE.exists():
        print("Daemon: ZATRZYMANY (brak PID file)")
        return
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, 0)
        inbox = list(INBOX_DIR.glob("*.json")) + list(INBOX_DIR.glob("*.yaml"))
        processing = list(PROCESSING_DIR.glob("*.json")) + list(PROCESSING_DIR.glob("*.yaml"))
        outbox = list(OUTBOX_DIR.glob("*.json"))
        failed = list(FAILED_DIR.glob("*.json"))
        print(f"Daemon: DZIAŁA (PID {pid})")
        print(f"  inbox:      {len(inbox)}")
        print(f"  processing: {len(processing)}")
        print(f"  outbox:     {len(outbox)}")
        print(f"  failed:     {len([f for f in failed if not f.name.endswith('.error.json')])}")
    except ProcessLookupError:
        print(f"Daemon: MARTWY (PID {pid} nie istnieje)")
        PID_FILE.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Manager Daemon — kolejka zadań agenta")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--start", action="store_true", help="Uruchom daemon (foreground)")
    group.add_argument("--stop", action="store_true", help="Zatrzymaj daemon przez SIGTERM")
    group.add_argument("--status", action="store_true", help="Status daemona i kolejki")
    args = parser.parse_args()

    if args.stop:
        cmd_stop()
    elif args.status:
        cmd_status()
    else:
        cmd_start()


if __name__ == "__main__":
    main()
