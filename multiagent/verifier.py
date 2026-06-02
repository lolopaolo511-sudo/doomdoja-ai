#!/usr/bin/env python3
"""
VERIFIER — twarda weryfikacja artefaktów po implementacji.

Działanie:
  Wykrywa typ artefaktu (Python / HTML / JS / JSON / Generic)
  i uruchamia odpowiednie sprawdzenia:

  Python → py_compile (składnia) + pytest (testy jeśli obecne)
  HTML   → kompletność struktury + sprawdzenia specyficzne dla gier
           (canvas, requestAnimationFrame, tagi script)
  JS     → node --check (jeśli node dostępny), fallback: heurystyki
  JSON   → json.loads
  Generic→ brak specyficznej weryfikacji (pass)

Użycie:
    from multiagent.verifier import Verifier

    v = Verifier(max_fix_rounds=3)
    result = v.verify_path(Path("index.html"))
    if not result.passed:
        print(result.summary())
        print(result.fix_hint)
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class VerificationResult:
    passed: bool
    artifact_type: str
    details: str = ""
    errors: list[str] = field(default_factory=list)
    fix_hint: str = ""     # instrukcja dla codera jak naprawić
    test_output: str = ""  # surowy output testów

    def __bool__(self) -> bool:
        return self.passed

    def summary(self) -> str:
        status = "✓ PASS" if self.passed else "✗ FAIL"
        lines = [f"[VERIFIER] {status} ({self.artifact_type})"]
        for e in self.errors[:8]:
            lines.append(f"  ERROR: {e}")
        if self.details:
            lines.append(f"  {self.details}")
        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "artifact_type": self.artifact_type,
            "errors": self.errors,
            "details": self.details,
            "fix_hint": self.fix_hint,
        }


# ── DETEKCJA TYPU ─────────────────────────────────────────────────────────────

_EXT_MAP = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".html": "html", ".htm": "html",
    ".json": "json",
    ".ts": "typescript",
    ".sh": "shell",
}


def detect_type(path: Path) -> str:
    return _EXT_MAP.get(path.suffix.lower(), "generic")


# ── WERYFIKACJA PYTHON ────────────────────────────────────────────────────────

def verify_python(path: Path) -> VerificationResult:
    errors: list[str] = []

    # 1. Składnia przez ast.parse
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
    except SyntaxError as e:
        hint = f"Napraw błąd składni Python w linii {e.lineno}: {e.msg}"
        return VerificationResult(
            False, "python",
            f"Syntax error at line {e.lineno}",
            [f"SyntaxError L{e.lineno}: {e.msg}"],
            fix_hint=hint,
        )

    # 2. py_compile dla głębszego sprawdzenia
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        err = result.stderr.strip()
        errors.append(f"py_compile: {err}")

    # 3. pytest jeśli pliki testów istnieją
    work_dir = path.parent
    test_files = list(work_dir.glob("test_*.py")) + list(work_dir.glob("*_test.py"))
    test_passed = True
    test_output = ""

    if test_files:
        pr = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short", "--no-header"],
            capture_output=True, text=True, timeout=60, cwd=work_dir,
        )
        test_output = (pr.stdout + pr.stderr).strip()
        test_passed = pr.returncode == 0
        if not test_passed:
            failed_lines = [l for l in test_output.splitlines() if "FAILED" in l or "ERROR" in l]
            errors.extend(failed_lines[:5])
            errors.append(f"pytest exit {pr.returncode}")

    passed = not errors and test_passed
    details = f"Syntax OK. Testy: {'brak' if not test_files else ('PASS' if test_passed else 'FAIL')}."

    fix_hint = ""
    if errors:
        fix_hint = "Napraw błędy pytest:\n" + "\n".join(errors[:5])

    return VerificationResult(passed, "python", details, errors,
                              fix_hint=fix_hint, test_output=test_output)


# ── WERYFIKACJA HTML ──────────────────────────────────────────────────────────

# Słowa kluczowe sugerujące grę (trigger dla sprawdzeń canvas/game-loop)
_GAME_KEYWORDS = {"game", "tower", "mario", "icy", "snake", "tetris", "pong",
                  "breakout", "platformer", "arcade", "shooter", "puzzle"}


def _is_game_html(path: Path, source: str) -> bool:
    name_lower = path.stem.lower()
    # Sprawdź nazwę pliku i katalogu nadrzędnego (np. ~/IcyTower3/index.html)
    parent_lower = path.parent.name.lower()
    if any(kw in name_lower or kw in parent_lower for kw in _GAME_KEYWORDS):
        return True
    if "<canvas" in source.lower():
        return True
    return False


def verify_html(path: Path) -> VerificationResult:
    source = path.read_text(encoding="utf-8")
    errors: list[str] = []
    src_lower = source.lower()

    # — Podstawowa struktura HTML —
    struct_checks = [
        ("<!doctype", "Brak deklaracji <!DOCTYPE html>"),
        ("<html", "Brak otwierającego tagu <html>"),
        ("</html>", "Brak zamykającego tagu </html>"),
        ("<head", "Brak sekcji <head>"),
        ("<body", "Brak sekcji <body>"),
    ]
    for pattern, msg in struct_checks:
        if pattern not in src_lower:
            errors.append(msg)

    # — Sprawdzenia specyficzne dla gry —
    if _is_game_html(path, source):
        game_checks = [
            ("<canvas", "Brak elementu <canvas> (wymagany dla gry)"),
            ("getcontext", "Brak canvas.getContext() — canvas nie zainicjowany"),
            ("requestanimationframe", "Brak requestAnimationFrame() — brak pętli gry"),
            ("<script", "Brak kodu JavaScript (<script>) — gra nie ma logiki"),
        ]
        for pattern, msg in game_checks:
            if pattern not in src_lower:
                errors.append(msg)

    # — Parowanie tagów script —
    open_scripts = len(re.findall(r'<script[^>]*>', source, re.IGNORECASE))
    close_scripts = len(re.findall(r'</script>', source, re.IGNORECASE))
    if open_scripts != close_scripts:
        errors.append(
            f"Nieparzyste tagi <script>: {open_scripts} otwartych, {close_scripts} zamkniętych"
        )

    # — Weryfikacja składni JS w blokach <script> —
    script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', source, re.DOTALL | re.IGNORECASE)
    js_errors: list[str] = []

    if shutil.which("node"):
        for i, block in enumerate(script_blocks, 1):
            if not block.strip():
                continue
            with tempfile.NamedTemporaryFile(mode="w", suffix=".js",
                                             delete=False, encoding="utf-8") as f:
                f.write(block)
                tmp = Path(f.name)
            try:
                r = subprocess.run(
                    ["node", "--check", str(tmp)],
                    capture_output=True, text=True, timeout=10,
                )
                if r.returncode != 0:
                    err = r.stderr.strip().splitlines()[0] if r.stderr else "syntax error"
                    js_errors.append(f"Blok JS #{i}: {err}")
            finally:
                tmp.unlink(missing_ok=True)
    else:
        # Fallback bez node: podstawowe heurystyki
        for i, block in enumerate(script_blocks, 1):
            if not block.strip():
                continue
            # Sprawdź parowanie nawiasów klamrowych
            opens = block.count("{")
            closes = block.count("}")
            if abs(opens - closes) > 2:
                js_errors.append(
                    f"Blok JS #{i}: nierównowaga nawiasów {{{opens} vs }}{closes}"
                )
            # Sprawdź niezamknięte literały stringowe (bardzo podstawowo)
            # (pomijamy — za dużo false positives)

    errors.extend(js_errors)

    # — Minimalna zawartość —
    if not source.strip():
        errors.append("Plik jest pusty")

    passed = len(errors) == 0
    size_kb = len(source.encode()) // 1024
    details = (
        f"HTML: {size_kb}KB, {len(script_blocks)} bloków JS, "
        f"canvas={'TAK' if '<canvas' in src_lower else 'NIE'}"
    )

    fix_hint = ""
    if errors:
        fix_hint = (
            "Napraw następujące problemy w pliku HTML/JS:\n"
            + "\n".join(f"- {e}" for e in errors)
        )

    return VerificationResult(passed, "html", details, errors, fix_hint=fix_hint)


# ── WERYFIKACJA JAVASCRIPT ────────────────────────────────────────────────────

def verify_javascript(path: Path) -> VerificationResult:
    errors: list[str] = []

    if shutil.which("node"):
        r = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            err = r.stderr.strip()
            errors.append(err[:300])
        passed = r.returncode == 0
        details = "node --check OK" if passed else "node --check FAIL"
    else:
        # Bez node: podstawowe sprawdzenie par nawiasów
        source = path.read_text(encoding="utf-8")
        opens = source.count("{")
        closes = source.count("}")
        passed = abs(opens - closes) <= 2
        if not passed:
            errors.append(f"Nierównowaga nawiasów: {{{opens} vs }}{closes}")
        details = "heuristic check (node nie zainstalowany)"

    fix_hint = "Napraw błąd składni JavaScript:\n" + "\n".join(errors) if errors else ""
    return VerificationResult(passed, "javascript", details, errors, fix_hint=fix_hint)


# ── WERYFIKACJA JSON ──────────────────────────────────────────────────────────

def verify_json(path: Path) -> VerificationResult:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VerificationResult(True, "json", f"Valid JSON ({type(data).__name__})", [])
    except json.JSONDecodeError as e:
        hint = f"Napraw błąd JSON w linii {e.lineno}, kolumna {e.colno}: {e.msg}"
        return VerificationResult(False, "json", "Invalid JSON", [str(e)], fix_hint=hint)


# ── WERYFIKACJA POWŁOKI ───────────────────────────────────────────────────────

def verify_shell(path: Path) -> VerificationResult:
    if shutil.which("bash"):
        r = subprocess.run(
            ["bash", "-n", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        errors = [r.stderr.strip()] if r.returncode != 0 and r.stderr.strip() else []
        return VerificationResult(r.returncode == 0, "shell",
                                  "bash -n OK" if not errors else "syntax error", errors)
    return VerificationResult(True, "shell", "bash not available", [])


# ── GŁÓWNY INTERFACE ──────────────────────────────────────────────────────────

class Verifier:
    """
    Twardy etap weryfikacji po implementacji.

    Użycie:
        v = Verifier(max_fix_rounds=3)
        result = v.verify_path(Path("index.html"))
        result = v.verify_directory(work_dir)   # wszystkie pliki w katalogu
    """

    def __init__(self, max_fix_rounds: int = 3):
        self.max_fix_rounds = max_fix_rounds

    def verify_path(self, path: Path) -> VerificationResult:
        """Zweryfikuj jeden plik."""
        if not path.exists():
            return VerificationResult(
                False, "missing",
                f"Plik nie istnieje: {path}",
                [f"File not found: {path}"],
                fix_hint=f"Utwórz plik: {path}",
            )

        artifact_type = detect_type(path)
        dispatch = {
            "python": verify_python,
            "html": verify_html,
            "javascript": verify_javascript,
            "json": verify_json,
            "shell": verify_shell,
        }
        fn = dispatch.get(artifact_type)
        if fn:
            return fn(path)
        return VerificationResult(True, artifact_type, "Brak weryfikacji dla tego typu", [])

    def verify_directory(self, work_dir: Path) -> dict[str, VerificationResult]:
        """
        Zweryfikuj wszystkie pliki w katalogu.

        Wyklucza: pliki ukryte, __pycache__, .venv, test_*.py, *_test.py
        (testy weryfikowane są razem z modułem który testują).
        """
        results: dict[str, VerificationResult] = {}
        skip_suffixes = {".pyc", ".pyo", ".pyd"}
        skip_names = {"__pycache__", ".venv", "venv", ".git", "node_modules"}

        for p in sorted(work_dir.iterdir()):
            if p.name.startswith(".") or p.name in skip_names:
                continue
            if p.is_dir():
                continue
            if p.suffix in skip_suffixes:
                continue
            if p.suffix not in _EXT_MAP:
                continue
            results[p.name] = self.verify_path(p)

        return results

    def verify_and_report(self, work_dir: Path) -> tuple[bool, str]:
        """
        Zweryfikuj katalog i zwróć (overall_passed, report_string).

        Używane przez orchestrator.
        """
        results = self.verify_directory(work_dir)
        if not results:
            # Brak plików do weryfikacji — sprawdź czy katalog w ogóle ma coś
            all_files = list(work_dir.iterdir()) if work_dir.exists() else []
            if not all_files:
                return False, "[VERIFIER] Katalog roboczy jest pusty — brak artefaktów"
            return True, "[VERIFIER] Brak plików do weryfikacji (typy nieobsługiwane)"

        lines = ["[VERIFIER] Raport weryfikacji:"]
        overall_passed = True

        for fname, result in results.items():
            icon = "✓" if result.passed else "✗"
            lines.append(f"  [{icon}] {fname} ({result.artifact_type})")
            if result.errors:
                for e in result.errors[:4]:
                    lines.append(f"       ERROR: {e}")
            if not result.passed:
                overall_passed = False

        status = "✓ PASS" if overall_passed else "✗ FAIL"
        lines.append(f"\n[VERIFIER] STATUS: {status} ({sum(r.passed for r in results.values())}/{len(results)} plików OK)")

        return overall_passed, "\n".join(lines)

    def collect_fix_hints(self, work_dir: Path) -> str:
        """Zbierz wskazówki naprawcze ze wszystkich niesprawnych plików."""
        results = self.verify_directory(work_dir)
        hints = []
        for fname, result in results.items():
            if not result.passed and result.fix_hint:
                hints.append(f"=== {fname} ===\n{result.fix_hint}")
        return "\n\n".join(hints) if hints else ""


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Weryfikator artefaktów qwen-agent")
    parser.add_argument("path", help="Ścieżka do pliku lub katalogu")
    args = parser.parse_args()

    verifier = Verifier()
    target = Path(args.path)

    if target.is_dir():
        passed, report = verifier.verify_and_report(target)
        print(report)
        sys.exit(0 if passed else 1)
    else:
        result = verifier.verify_path(target)
        print(result.summary())
        if result.fix_hint:
            print(f"\nWskazówka naprawcza:\n{result.fix_hint}")
        sys.exit(0 if result.passed else 1)
