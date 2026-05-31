#!/usr/bin/env python3
"""
Autonomiczna pętla agentowa: zadanie → aider → pytest → commit
Użycie: python3 agent_runner.py --repo /ścieżka/do/repo [--max-retries 3]
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

AGENT_DIR = Path(__file__).parent
TASKS_DIR = AGENT_DIR / "tasks"
LOGS_DIR = AGENT_DIR / "logs"

AIDER_BIN = Path.home() / "Library/Python/3.9/bin/aider"
AIDER_MODEL = "ollama_chat/deepseek-coder-v2:16b"


def setup_logging(repo_path: Path) -> logging.Logger:
    log_file = LOGS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("agent")
    logger.info(f"Log: {log_file}")
    return logger


def pick_next_task() -> Optional[Path]:
    pending = sorted((TASKS_DIR / "pending").glob("*.txt"))
    return pending[0] if pending else None


def run_aider(task_text: str, repo: Path, logger: logging.Logger) -> bool:
    cmd = [
        str(AIDER_BIN),
        "--model", AIDER_MODEL,
        "--edit-format", "whole",  # bezpieczniejszy dla pustych/nowych plików
        "--yes",
        "--no-auto-commits",
        "--message", task_text,
    ]
    logger.info(f"Uruchamiam aider: {' '.join(cmd[:4])} ... (w {repo})")
    result = subprocess.run(
        cmd,
        cwd=repo,
        capture_output=False,
        text=True,
        timeout=300,
        env={**os.environ, "PATH": f"/Users/doomdoja/Library/Python/3.9/bin:{os.environ.get('PATH', '')}"},
    )
    logger.info(f"Aider exit code: {result.returncode}")
    return result.returncode == 0


def run_tests(repo: Path, logger: logging.Logger) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    passed = result.returncode == 0
    logger.info(f"Pytest {'PASSED' if passed else 'FAILED'} (exit {result.returncode})")
    if not passed:
        logger.info(f"Pytest output:\n{output[-2000:]}")
    return passed, output


def git_commit(repo: Path, message: str, logger: logging.Logger) -> bool:
    try:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo, capture_output=True, text=True,
        )
        if result.returncode == 0:
            logger.info(f"Commit stworzony: {message}")
            return True
        else:
            logger.warning(f"Commit failed: {result.stderr.strip()}")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Git error: {e}")
        return False


def process_task(task_file: Path, repo: Path, max_retries: int, logger: logging.Logger) -> bool:
    task_text = task_file.read_text().strip()
    task_name = task_file.stem
    logger.info(f"=== Zadanie: {task_name} ===")
    logger.info(f"Treść: {task_text[:200]}")

    for attempt in range(1, max_retries + 1):
        logger.info(f"--- Próba {attempt}/{max_retries} ---")

        aider_ok = run_aider(task_text, repo, logger)
        if not aider_ok:
            logger.warning("Aider zakończył z błędem, próbuję testy mimo to...")

        tests_ok, test_output = run_tests(repo, logger)

        if tests_ok:
            commit_msg = f"agent: {task_name} (próba {attempt})\n\nZadanie: {task_text[:200]}"
            git_commit(repo, commit_msg, logger)
            shutil.move(str(task_file), str(TASKS_DIR / "done" / task_file.name))
            logger.info(f"SUKCES: zadanie {task_name} ukończone po {attempt} próbach")
            return True

        if attempt < max_retries:
            # Przekaż błędy testów do aidera jako follow-up
            fix_msg = f"Testy nie przeszły. Napraw błędy:\n\n{test_output[-1500:]}"
            logger.info("Przekazuję błędy testów do aidera...")
            run_aider(fix_msg, repo, logger)

    logger.error(f"PORAŻKA: zadanie {task_name} nie ukończone po {max_retries} próbach")
    shutil.move(str(task_file), str(TASKS_DIR / "failed" / task_file.name))
    return False


def main():
    parser = argparse.ArgumentParser(description="Autonomiczna pętla agentowa qwen/aider")
    parser.add_argument("--repo", required=True, help="Ścieżka do repozytorium git")
    parser.add_argument("--max-retries", type=int, default=3, help="Max prób na zadanie (domyślnie: 3)")
    parser.add_argument("--run-all", action="store_true", help="Przetwórz wszystkie zadania z kolejki")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"BŁĄD: {repo} nie jest repozytorium git (brak .git)")
        sys.exit(1)

    LOGS_DIR.mkdir(exist_ok=True)
    logger = setup_logging(repo)
    logger.info(f"Repo: {repo} | Max prób: {args.max_retries}")

    if args.run_all:
        processed = 0
        task = pick_next_task()
        while task is not None:
            process_task(task, repo, args.max_retries, logger)
            processed += 1
            task = pick_next_task()
        logger.info(f"Przetworzono {processed} zadań")
    else:
        task = pick_next_task()
        if not task:
            logger.info("Brak zadań w kolejce (tasks/pending/*.txt)")
            sys.exit(0)
        success = process_task(task, repo, args.max_retries, logger)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
