#!/usr/bin/env python3
"""
Manager Daemon — obserwuje inbox/, przetwarza zadania przez lokalnego agenta.

Tryby:
  local  — wymusza model Ollama, bez routera
  auto   — HybridRouter decyduje local/cloud

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
    "status": "done",
    "output": "...",
    "model_used": "deepseek-coder-v2:16b",
    "backend": "local",
    "tokens_estimated": 150,
    "duration_s": 3.2,
    "verifier_passed": true,
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


# ── PRZETWARZANIE ZADANIA ─────────────────────────────────────────────────────

def process_task(data: dict) -> dict:
    """Przetwarza jedno zadanie, zwraca słownik wyniku."""
    task_id = data["id"]
    task_text = data["task"]
    mode = data.get("mode", "auto")
    max_tokens: Optional[int] = data.get("max_tokens")
    priority = data.get("priority", 5)

    logger.info(f"[{task_id}] START mode={mode} priority={priority} len={len(task_text)}")
    t0 = time.monotonic()

    backend_name = "local"
    model_used = "deepseek-coder-v2:16b"
    verifier_passed = False
    output = ""
    error_msg: Optional[str] = None

    try:
        if mode == "local":
            # Wymuś lokalny backend
            from router.backends.local import LocalBackend
            local_be = LocalBackend()
            output = local_be.generate(task_text, max_tokens=max_tokens)
            backend_name = "local"
            model_used = _get_local_model()

        elif mode == "auto":
            # Router decyduje
            from router import HybridRouter, RouterContext
            router = HybridRouter()
            ctx = RouterContext(
                step_title=task_text[:80],
                force_local=False,
                force_cloud=False,
            )
            decision = router.choose_model(task_text, ctx)
            backend_name = decision.backend
            model_used = decision.model
            logger.info(f"[{task_id}] Router: {decision.summary()}")

            if decision.backend == "local":
                from router.backends.local import LocalBackend
                local_be = LocalBackend()
                output = local_be.generate(task_text, model=decision.model, max_tokens=max_tokens)
            else:
                # Eskalacja do cloud
                from router.backends.cloud import CloudBackend
                cloud_be = CloudBackend()
                output = cloud_be.generate(task_text, model=decision.model, max_tokens=max_tokens)

        # Podstawowa weryfikacja — sprawdź czy odpowiedź nie jest pusta
        verifier_passed = bool(output and output.strip())

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error(f"[{task_id}] BŁĄD: {error_msg}")

    duration = time.monotonic() - t0
    tokens_estimated = len(output.split()) if output else 0

    result = {
        "id": task_id,
        "status": "done" if not error_msg else "failed",
        "output": output,
        "model_used": model_used,
        "backend": backend_name,
        "tokens_estimated": tokens_estimated,
        "duration_s": round(duration, 3),
        "verifier_passed": verifier_passed,
        "error": error_msg,
        "completed_at": datetime.now().isoformat(),
        "task_preview": task_text[:120],
    }

    logger.info(
        f"[{task_id}] {'DONE' if not error_msg else 'FAIL'} "
        f"backend={backend_name} model={model_used} "
        f"tokens~{tokens_estimated} t={duration:.2f}s"
    )
    return result


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

    def start(self):
        setup_logging()
        logger.info("=== Manager Daemon URUCHOMIONY ===")
        logger.info(f"  inbox:      {INBOX_DIR}")
        logger.info(f"  outbox:     {OUTBOX_DIR}")
        logger.info(f"  poll:       {POLL_INTERVAL_S}s")

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
            INBOX_DIR.glob("*.json") | INBOX_DIR.glob("*.yaml") | INBOX_DIR.glob("*.yml"),
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

        # Zapis do outbox/ lub failed/
        task_id = data["id"]
        if result["status"] == "done":
            out_path = OUTBOX_DIR / f"{task_id}.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"Wynik zapisany: {out_path}")
        else:
            self._move_to_failed(proc_file, result.get("error") or "unknown error", result)

        # Usuń plik z processing/
        proc_file.unlink(missing_ok=True)

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
