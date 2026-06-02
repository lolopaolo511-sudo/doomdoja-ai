#!/usr/bin/env python3
"""
Demo hybrydowego routera — 3 przykłady decyzji.

Uruchomienie:
    python3 ~/qwen-agent/router/demo.py

Nie wymaga połączenia z Ollama ani kluczy API.
Pokazuje tylko logikę decyzyjną routera (bez realnego generowania).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from router.router import HybridRouter, RouterContext

BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
RESET = "\033[0m"

def header(title: str) -> None:
    print(f"\n{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{'─'*60}")

def show_decision(label: str, decision) -> None:
    backend_color = CYAN if decision.backend == "cloud" else GREEN
    backend_icon = "☁️  CLOUD" if decision.backend == "cloud" else "🏠 LOCAL"
    print(f"  Backend : {backend_color}{BOLD}{backend_icon}{RESET}")
    print(f"  Model   : {decision.model}")
    print(f"  Score   : {decision.complexity_score}")
    print(f"  Powód   : {decision.reason}")
    if decision.privacy_protected:
        print(f"  {RED}{BOLD}⚠️  PRIVACY PROTECTED — dane wrażliwe, zawsze local{RESET}")
    if decision.escalated:
        print(f"  {YELLOW}{BOLD}⬆️  ESCALATED — verifier zawiódł zbyt wiele razy{RESET}")
    if not decision.cloud_available and decision.backend == "local":
        print(f"  {YELLOW}ℹ️  Cloud niedostępny (brak ANTHROPIC_API_KEY){RESET}")

def make_router_with_key(has_key: bool) -> HybridRouter:
    """Tworzy router z mockowaną obecnością klucza API."""
    router = HybridRouter()
    available = bool(has_key)
    router._is_cloud_available = lambda: available
    router._cloud_available = available
    return router


def main():
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}   HYBRID ROUTER — Demo decyzji (3 przykłady)   {RESET}")
    print(f"{BOLD}{'═'*60}{RESET}")
    print("  Nie wymaga połączenia z Ollama ani kluczy API.")
    print("  Pokazuje logikę decyzyjną routera na realnych przypadkach.")

    # ──────────────────────────────────────────────────────────────
    # PRZYKŁAD 1: Prosty skrypt → local
    # ──────────────────────────────────────────────────────────────
    header("Przykład 1: Prosty skrypt → LOCAL")

    router1 = make_router_with_key(has_key=True)  # klucz dostępny, ale zadanie proste
    task1 = "napisz prosty skrypt Python który konwertuje listę do stringa"

    print(f"  Zadanie : {BOLD}{task1!r}{RESET}")
    ctx1 = RouterContext(step_id=1, step_title="simple-convert", plan_steps_total=1)
    d1 = router1.choose_model(task1, context=ctx1)
    show_decision("Przykład 1", d1)

    print(f"\n  {GREEN}✓ Wynik zgodny z oczekiwaniem: prosta konwersja → local (oszczędność)")
    print(f"    Fast model: {router1.local_fast_model} (szybszy, tańszy){RESET}")

    # ──────────────────────────────────────────────────────────────
    # PRZYKŁAD 2a: Złożona aplikacja → cloud (klucz dostępny)
    # ──────────────────────────────────────────────────────────────
    header("Przykład 2a: Złożona aplikacja → CLOUD (klucz dostępny)")

    router2a = make_router_with_key(has_key=True)
    task2 = (
        "Design and implement a full application for lead management: "
        "microservice architecture, integration with external APIs, database PostgreSQL, "
        "task queue system, automatic retries, monitoring and deployment pipeline. "
        "Include integration tests and API documentation. "
        "Optimize for concurrent requests and implement caching strategy. "
        "Add CI/CD pipeline with Kubernetes orchestration and infrastructure-as-code."
    )

    print(f"  Zadanie : (>{len(task2)} znaków, wiele słów kluczowych architektura/database/deployment...)")
    ctx2 = RouterContext(step_id=1, step_title="full-app-design", plan_steps_total=7)
    d2a = router2a.choose_model(task2, context=ctx2)
    show_decision("Przykład 2a", d2a)

    print(f"\n  {CYAN}✓ Wynik: score wysoki ({d2a.complexity_score}) + klucz dostępny → cloud")
    print(f"    Model cloud: {router2a.cloud_model}{RESET}")

    # PRZYKŁAD 2b: Eskalacja po porażkach verifier
    header("Przykład 2b: Eskalacja po 2 porażkach verifier → CLOUD")

    router2b = make_router_with_key(has_key=True)
    task2b = "napraw błędy składni w module parsera"

    print(f"  Zadanie : {BOLD}{task2b!r}{RESET}")
    print(f"  Kontekst: verifier zawiódł już {router2b.verifier_fails_escalate}× (próg={router2b.verifier_fails_escalate})")

    ctx2b = RouterContext(
        step_id=3,
        step_title="parser-fix",
        verifier_fails=router2b.verifier_fails_escalate,
        plan_steps_total=2,
    )
    d2b = router2b.choose_model(task2b, context=ctx2b)
    show_decision("Przykład 2b", d2b)

    print(f"\n  {CYAN}✓ Wynik: prosta treść ALE eskalacja po {router2b.verifier_fails_escalate} porażkach verifier → cloud")
    print(f"    Po sukcesie coder wraca do lokalnego modelu dla kolejnych kroków{RESET}")

    # PRZYKŁAD 2c: Złożona aplikacja BEZ klucza → local-only
    header("Przykład 2c: Złożona aplikacja BEZ klucza → LOCAL-ONLY mode")

    router2c = make_router_with_key(has_key=False)
    print(f"  Zadanie : (to samo co 2a: duże, złożone, architektura+database+deployment)")
    ctx2c = RouterContext(step_id=1, plan_steps_total=7)
    d2c = router2c.choose_model(task2, context=ctx2c)
    show_decision("Przykład 2c", d2c)

    print(f"\n  {YELLOW}ℹ️  Wynik: score={d2c.complexity_score} ≥ próg={router2c.score_cloud}, ale brak ANTHROPIC_API_KEY")
    print(f"    → pozostaje local, loguje ostrzeżenie, nie crashuje{RESET}")

    # ──────────────────────────────────────────────────────────────
    # PRZYKŁAD 3: Dane wrażliwe → force-local (zawsze, bez wyjątku)
    # ──────────────────────────────────────────────────────────────
    header("Przykład 3: Dane wrażliwe → FORCE-LOCAL (privacy override)")

    router3 = make_router_with_key(has_key=True)

    cases = [
        ("System zarządzania hasłami (password manager) z szyfrowaniem", "hasł/password"),
        ("Walidacja numeru PESEL w formularzu rejestracji klienta",      "pesel"),
        ("Endpoint zwracający secret token Bearer authorization",         "secret/token/bearer"),
    ]

    all_local = True
    for task_text, kw_desc in cases:
        # Nawet z force_cloud=True i wysokim score → prywatność wygrywa
        ctx3 = RouterContext(force_cloud=True, verifier_fails=5)
        d3 = router3.choose_model(task_text, context=ctx3)
        icon = "✓" if (d3.backend == "local" and d3.privacy_protected) else "✗"
        color = GREEN if icon == "✓" else RED
        print(f"  {color}{icon}{RESET} [{kw_desc}] → {d3.backend.upper()} | {d3.reason}")
        if d3.backend != "local":
            all_local = False

    result_msg = (
        f"{GREEN}✓ Wszystkie wrażliwe zadania trafiły do LOCAL (prywatność > wszystko)"
        if all_local
        else f"{RED}✗ BŁĄD: wrażliwe zadanie trafiło do cloud!"
    )
    print(f"\n  {result_msg}{RESET}")

    # ──────────────────────────────────────────────────────────────
    # RAPORT KOŃCOWY SESJI (przykład 3)
    # ──────────────────────────────────────────────────────────────
    header("Raport routera z sesji (przykład 3)")
    print(router3.get_report())

    # ──────────────────────────────────────────────────────────────
    # PODSUMOWANIE DEMO
    # ──────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}   PODSUMOWANIE DEMO{RESET}")
    print(f"{'═'*60}")
    rows = [
        ("Prosty skrypt", "local", f"score={d1.complexity_score}", "✓"),
        ("Złożona aplikacja (klucz)", "cloud", f"score={d2a.complexity_score}", "✓"),
        ("Eskalacja verifier ×2", "cloud", "escalated", "✓"),
        ("Złożona aplikacja (brak klucza)", "local", "local-only mode", "✓"),
        ("Dane wrażliwe + force_cloud", "local", "privacy override", "✓"),
    ]
    print(f"  {'Przypadek':<35} {'Backend':<8} {'Info':<20} {'OK'}")
    print(f"  {'─'*35} {'─'*8} {'─'*20} {'─'*4}")
    for case, backend, info, ok in rows:
        bc = CYAN if backend == "cloud" else GREEN
        print(f"  {case:<35} {bc}{backend:<8}{RESET} {info:<20} {GREEN}{ok}{RESET}")

    print(f"\n  {BOLD}Ustaw ANTHROPIC_API_KEY aby aktywować cloud fallback:{RESET}")
    print(f"  export ANTHROPIC_API_KEY=sk-ant-...   # lub dodaj do .env")
    print(f"\n  {BOLD}Wymuszenie local dla całego zadania:{RESET}")
    print(f"  python3 orchestrator.py 'zadanie' --force-local")
    print()


if __name__ == "__main__":
    main()
