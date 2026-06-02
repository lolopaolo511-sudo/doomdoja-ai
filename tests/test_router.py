#!/usr/bin/env python3
"""
Testy jednostkowe logiki routingu — BEZ realnego cloud (mock).

Pokrycie:
  1. Proste zadanie → local
  2. Złożone zadanie → cloud (gdy klucz dostępny)
  3. Złożone zadanie bez klucza → local-only (z ostrzeżeniem)
  4. Dane wrażliwe → force-local, nigdy cloud
  5. Eskalacja po N porażkach verifier → cloud
  6. force_local flag → zawsze local
  7. force_cloud flag → cloud (o ile brak prywatności)
  8. force_cloud + dane wrażliwe → local (prywatność wygrywa)
  9. Wynik złożoności: długi tekst
  10. Raport końcowy zawiera wpisy
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Dodaj root projektu do path
_ROOT = str(Path(__file__).parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from router.router import HybridRouter, RouterContext, reset_router


# ── FIXTURE ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_router():
    """Każdy test dostaje świeżą instancję routera bez stanu."""
    reset_router()
    yield
    reset_router()


def make_router(has_cloud_key: bool = False, config: dict | None = None) -> HybridRouter:
    """Tworzy router z mockowanym dostępem do klucza cloud."""
    env_val = "sk-mock-test-key" if has_cloud_key else ""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": env_val}):
        router = HybridRouter(config=config)
        router._cloud_available = None  # wymuś re-check przez _is_cloud_available
    # Patch os.getenv na poziomie routera
    router._get_key_patch = env_val
    # Monkey-patch _is_cloud_available dla spójności bez realnego os.environ
    original_check = router._is_cloud_available

    def patched_check():
        router._cloud_available = bool(env_val)
        if not router._cloud_available:
            import logging
            logging.getLogger("qwen_agent.router").warning(
                f"[router] LOCAL-ONLY MODE: {router._api_key_env} not set"
            )
        return router._cloud_available

    router._is_cloud_available = patched_check
    return router


# ── TESTY ─────────────────────────────────────────────────────────────────────

class TestSimpleTasks:
    def test_simple_task_goes_local(self):
        """Krótkie, proste zadanie → local."""
        router = make_router(has_cloud_key=True)
        decision = router.choose_model("napisz prosty skrypt print hello world")
        assert decision.backend == "local", f"Oczekiwano local, dostałem: {decision.backend} ({decision.reason})"
        assert decision.complexity_score < router.score_cloud

    def test_simple_task_uses_fast_model(self):
        """Bardzo prosta, krótka fraza → qwen fast model."""
        router = make_router(has_cloud_key=True)
        decision = router.choose_model("convert list to set")
        assert decision.backend == "local"
        assert decision.model == router.local_fast_model

    def test_medium_task_local_no_key(self):
        """Średnie zadanie bez klucza cloud → local."""
        router = make_router(has_cloud_key=False)
        decision = router.choose_model(
            "Napisz klasę Python do parsowania pliku CSV z nagłówkami i zwracania listy słowników"
        )
        assert decision.backend == "local"
        assert not decision.cloud_available


class TestComplexTasks:
    def test_complex_task_goes_cloud(self):
        """Zadanie z architekturą/integracją + >500 znaków → cloud (klucz dostępny)."""
        router = make_router(has_cloud_key=True)
        # >500 znaków + wiele słów kluczowych → score >= próg
        task = (
            "Design and implement a full application for lead management: "
            "microservice architecture, integration with Airtable API, database PostgreSQL, "
            "system kolejkowania, automatic retries, monitoring i deployment na VPS. "
            "Include integration tests and documentation. Optimize for concurrent requests. "
            "System should handle at least 10,000 concurrent users, implement caching, "
            "load balancing and auto-scaling. Add CI/CD pipeline, Kubernetes orchestration "
            "and infrastructure-as-code with Terraform. Full application refactor included."
        )
        assert len(task) > 500, f"Task za krótki: {len(task)} znaków"
        decision = router.choose_model(task)
        assert decision.backend == "cloud", f"Oczekiwano cloud, dostałem local: {decision.reason} (score={decision.complexity_score})"
        assert decision.model == router.cloud_model

    def test_complex_task_no_key_falls_back_to_local(self):
        """Złożone zadanie bez klucza → local, cloud_available=False."""
        router = make_router(has_cloud_key=False)
        task = (
            "Design full application architecture with database integration, "
            "concurrent processing system, deployment pipeline and performance optimization. "
            "Include refactor of existing code, integration with external APIs, "
            "complex async processing, full application rewrite with microservice architecture. "
            "System needs database migration, deployment automation and monitoring setup."
        )
        decision = router.choose_model(task)
        assert decision.backend == "local"
        assert not decision.cloud_available
        # Gdy score >= próg ale brak klucza → komunikat "local-only" lub score < próg → "lokalny"
        assert decision.backend == "local"  # kluczowa asercja

    def test_many_steps_increases_score(self):
        """Wiele kroków z plannera podnosi wynik złożoności."""
        router = make_router(has_cloud_key=False)
        ctx = RouterContext(plan_steps_total=6)
        decision = router.choose_model("krótkie zadanie", context=ctx)
        assert decision.complexity_score >= 2, "plan_steps_total=6 powinien dodać punkty"


class TestPrivacyProtection:
    def test_password_in_task_forces_local(self):
        """Słowo 'hasło'/'hasłami' (rdzeń 'hasł') w zadaniu → zawsze local."""
        router = make_router(has_cloud_key=True)
        # Używam rdzenia "hasł" który pasuje do "hasło", "hasłami", "hasła" itd.
        decision = router.choose_model(
            "Napisz system zarządzania hasłami (password manager) dla klientów z AES-256"
        )
        assert decision.backend == "local"
        assert decision.privacy_protected

    def test_api_key_phrase_forces_local(self):
        """Fraza 'api_key' → force local."""
        router = make_router(has_cloud_key=True)
        decision = router.choose_model(
            "Rozbuduj moduł api_key do obsługi rotacji kluczy w systemie"
        )
        assert decision.backend == "local"
        assert decision.privacy_protected

    def test_secret_word_forces_local(self):
        router = make_router(has_cloud_key=True)
        decision = router.choose_model("przetestuj endpoint który zwraca secret token")
        assert decision.backend == "local"
        assert decision.privacy_protected

    def test_pesel_forces_local(self):
        router = make_router(has_cloud_key=True)
        decision = router.choose_model("walidacja numeru PESEL w formularzu rejestracji")
        assert decision.backend == "local"
        assert decision.privacy_protected

    def test_force_cloud_with_sensitive_data_still_local(self):
        """force_cloud NIE pokonuje ochrony prywatności."""
        router = make_router(has_cloud_key=True)
        ctx = RouterContext(force_cloud=True)
        decision = router.choose_model(
            "Zintegruj uwierzytelnianie przez token bearer z zewnętrznym API",
            context=ctx,
        )
        assert decision.backend == "local"
        assert decision.privacy_protected

    def test_force_local_flag_overrides_cloud(self):
        """force_local=True → zawsze local, nawet bez wrażliwych słów."""
        router = make_router(has_cloud_key=True)
        ctx = RouterContext(force_local=True)
        decision = router.choose_model(
            "Zaprojektuj całą architekturę systemu mikroserwisów z integracją bazy danych",
            context=ctx,
        )
        assert decision.backend == "local"
        assert not decision.privacy_protected  # to nie jest privacy, to force


class TestEscalation:
    def test_escalation_after_n_fails(self):
        """Po verifier_fails >= progu → eskalacja do cloud."""
        router = make_router(has_cloud_key=True)
        ctx = RouterContext(
            verifier_fails=router.verifier_fails_escalate,
            step_id=3,
            step_title="implementacja modułu",
        )
        decision = router.choose_model("napraw błędy w kodzie po testach", context=ctx)
        assert decision.backend == "cloud"
        assert decision.escalated

    def test_escalation_without_key_stays_local(self):
        """Eskalacja bez klucza → zostaje local (nie crash)."""
        router = make_router(has_cloud_key=False)
        ctx = RouterContext(verifier_fails=router.verifier_fails_escalate)
        decision = router.choose_model("napraw błędy testów", context=ctx)
        assert decision.backend == "local"
        assert not decision.cloud_available

    def test_no_escalation_below_threshold(self):
        """1 porażka verifier (poniżej progu) → bez eskalacji."""
        router = make_router(has_cloud_key=True)
        ctx = RouterContext(verifier_fails=router.verifier_fails_escalate - 1)
        decision = router.choose_model("simple fix after one fail", context=ctx)
        assert not decision.escalated

    def test_escalation_blocked_by_privacy(self):
        """Eskalacja + dane wrażliwe → local (prywatność wygrywa)."""
        router = make_router(has_cloud_key=True)
        ctx = RouterContext(verifier_fails=router.verifier_fails_escalate)
        # "password" to bezpośredni match (brak problemu z odmianą)
        decision = router.choose_model(
            "napraw błąd weryfikacji password w module logowania z secret token",
            context=ctx,
        )
        assert decision.backend == "local"
        assert decision.privacy_protected
        assert not decision.escalated


class TestReport:
    def test_report_has_entries(self):
        """Raport po kilku decyzjach zawiera wpisy."""
        router = make_router(has_cloud_key=True)
        router.choose_model("prosty print", context=RouterContext(step_id=1, step_title="init"))
        router.choose_model("token secret auth", context=RouterContext(step_id=2))
        report = router.get_report()
        assert "Krok 1" in report
        assert "Krok 2" in report
        assert "LOCAL" in report or "CLOUD" in report

    def test_report_empty_session(self):
        """Raport bez decyzji zwraca informację."""
        router = make_router(has_cloud_key=False)
        report = router.get_report()
        assert "Brak" in report

    def test_report_shows_privacy_marker(self):
        """Raport oznacza kroki z ochroną prywatności."""
        router = make_router(has_cloud_key=True)
        router.choose_model("ustaw hasło admina", context=RouterContext(step_id=5, step_title="auth"))
        report = router.get_report()
        assert "PRIVACY" in report

    def test_report_summary_counts(self):
        """Podsumowanie raportu ma poprawne liczniki."""
        router = make_router(has_cloud_key=True)
        router.choose_model("prosty skrypt", context=RouterContext(step_id=1))
        router.choose_model("hasło", context=RouterContext(step_id=2))
        report = router.get_report()
        assert "LOCAL=" in report


class TestComplexityScore:
    def test_long_task_increases_score(self):
        """Długie zadanie (>500 znaków) → wyższy wynik."""
        router = make_router(has_cloud_key=False)
        short = "napisz skrypt"
        long_task = "a" * 600
        d_short = router.choose_model(short)
        router2 = make_router(has_cloud_key=False)
        d_long = router2.choose_model(long_task)
        assert d_long.complexity_score > d_short.complexity_score

    def test_high_complexity_keywords_raise_score(self):
        """Wiele słów kluczowych wysokiej złożoności → score >= 4."""
        router = make_router(has_cloud_key=False)
        ctx = RouterContext()
        # Używamy angielskich form z config: "architecture", "database", "concurrent", "deployment"
        task = "design application architecture with database integration and concurrent system deployment"
        d = router.choose_model(task, context=ctx)
        assert d.complexity_score >= 4, (
            f"Oczekiwano score>=4, dostałem {d.complexity_score}. "
            f"Dopasowane kw: {[kw for kw in router._high_kw if kw in task.lower()]}"
        )

    def test_low_complexity_keywords_lower_score(self):
        router = make_router(has_cloud_key=False)
        d = router.choose_model("prosty convert listy do stringa")
        assert d.complexity_score <= 2
