#!/usr/bin/env python3
"""
Hybrid Router — automatyczny wybór backendu (local/cloud) per zadanie.

Sygnały decyzyjne:
  1. Złożoność zadania (długość, słowa-klucze, liczba kroków plannera)
  2. Flaga prywatności (force-local dla danych wrażliwych — nigdy do cloud)
  3. Historia verifiera (eskalacja po N nieudanych rundach lokalnych)
  4. Dostępność cloud API (brak klucza → local-only mode, loguje ostrzeżenie)

Użycie:
    from router.router import HybridRouter, RouterContext

    router = HybridRouter()
    decision = router.choose_model(task="napisz parser CSV", context=RouterContext())
    print(decision.backend, decision.model, decision.reason)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("qwen_agent.router")

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load_config() -> dict:
    try:
        import yaml
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Minimal YAML-less fallback — parse only simple key: value lines
        cfg: dict = {}
        _parse_yaml_lite(_CONFIG_PATH.read_text(encoding="utf-8"), cfg)
        return cfg
    except FileNotFoundError:
        logger.warning(f"Router config not found at {_CONFIG_PATH}, using defaults")
        return {}


def _parse_yaml_lite(text: str, target: dict) -> None:
    """Very basic YAML parser for flat key: scalar_value lines (fallback only)."""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line and not line.endswith(":"):
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            try:
                target[key.strip()] = int(val)
            except ValueError:
                try:
                    target[key.strip()] = float(val)
                except ValueError:
                    target[key.strip()] = val


@dataclass
class RouterContext:
    """Kontekst przekazywany do routera przy każdej decyzji."""
    step_id: Optional[int] = None
    step_title: str = ""
    plan_steps_total: int = 0
    verifier_fails: int = 0         # liczba nieudanych rund verifier DLA TEGO ZADANIA
    force_local: bool = False        # jawne wymuszenie lokalnego modelu
    force_cloud: bool = False        # jawne wymuszenie cloud (ignorowane jeśli prywatność)
    session_id: str = ""             # id sesji/zadania dla raportu


@dataclass
class RouterDecision:
    """Wynik decyzji routera."""
    backend: str                     # "local" | "cloud"
    model: str                       # nazwa modelu (Ollama lub cloud)
    provider: str                    # "ollama" | "anthropic"
    reason: str                      # wyjaśnienie dlaczego
    complexity_score: int = 0        # obliczony wynik złożoności
    privacy_protected: bool = False  # czy zablokowano ze względu na prywatność
    escalated: bool = False          # czy eskalacja z powodu porażek verifier
    cloud_available: bool = True     # czy cloud w ogóle jest dostępny

    def summary(self) -> str:
        icon = "☁️ CLOUD" if self.backend == "cloud" else "🏠 LOCAL"
        priv = " [PRIVACY-PROTECTED]" if self.privacy_protected else ""
        esc = " [ESCALATED]" if self.escalated else ""
        return (
            f"{icon} → {self.model}{priv}{esc} | "
            f"score={self.complexity_score} | {self.reason}"
        )


class HybridRouter:
    """
    Główny router. Instancja per sesja zadania — przechowuje historię decyzji.
    """

    def __init__(self, config: Optional[dict] = None):
        self._cfg = config or _load_config()
        self._cloud_available: Optional[bool] = None  # lazy check
        self._decisions: list[tuple[RouterContext, RouterDecision]] = []

        # Progi z configa (z fallback na sensowne domyślne)
        th = self._cfg.get("thresholds", {})
        self.score_cloud = int(th.get("complexity_score_cloud", 6))
        self.verifier_fails_escalate = int(th.get("verifier_fails_escalate", 2))
        self.task_length_complex = int(th.get("task_length_complex", 500))
        self.steps_complex = int(th.get("steps_complex", 4))
        self.max_score = int(th.get("max_complexity_score", 10))

        # Modele
        local_cfg = self._cfg.get("local", {})
        self.local_model = local_cfg.get("model", "deepseek-coder-v2:16b")
        self.local_fast_model = local_cfg.get("fast_model", "qwen2.5-coder:7b")

        cloud_cfg = self._cfg.get("cloud", {})
        self.cloud_model = cloud_cfg.get("model", "claude-opus-4-8")
        self.cloud_provider = cloud_cfg.get("provider", "anthropic")
        self._api_key_env = cloud_cfg.get("api_key_env", "ANTHROPIC_API_KEY")

        # Słowa-klucze
        priv_cfg = self._cfg.get("privacy", {})
        self._sensitive_kw: list[str] = [
            k.lower() for k in priv_cfg.get("sensitive_keywords", [])
        ]
        cmplx_cfg = self._cfg.get("complexity", {})
        self._high_kw: list[str] = [
            k.lower() for k in cmplx_cfg.get("high_complexity_keywords", [])
        ]
        self._low_kw: list[str] = [
            k.lower() for k in cmplx_cfg.get("low_complexity_keywords", [])
        ]

    # ── PUBLIC API ─────────────────────────────────────────────────────────

    def choose_model(self, task: str, context: Optional[RouterContext] = None) -> RouterDecision:
        """
        Główna funkcja decyzyjna.

        Args:
            task: treść zadania (lub kroku)
            context: opcjonalny kontekst (kroki, porażki verifier, flagi)

        Returns:
            RouterDecision z backendem, modelem i uzasadnieniem
        """
        ctx = context or RouterContext()
        task_lower = task.lower()

        # 1. SPRAWDZENIE PRYWATNOŚCI — absolutny priorytet
        privacy_hit = self._detect_sensitive(task_lower)
        if privacy_hit or ctx.force_local:
            reason = (
                f"force-local: wykryto wrażliwe słowo '{privacy_hit}'"
                if privacy_hit else "force-local: wymuszony przez context.force_local"
            )
            decision = RouterDecision(
                backend="local",
                model=self.local_model,
                provider="ollama",
                reason=reason,
                complexity_score=0,
                privacy_protected=bool(privacy_hit),
                cloud_available=self._is_cloud_available(),
            )
            self._log_and_record(ctx, decision)
            return decision

        # 2. OBLICZENIE ZŁOŻONOŚCI
        score = self._complexity_score(task, ctx)

        # 3. SPRAWDZENIE ESKALACJI VERIFIER
        escalated = ctx.verifier_fails >= self.verifier_fails_escalate and ctx.verifier_fails > 0

        # 4. WYMUSZENIE CLOUD przez flagę
        want_cloud = ctx.force_cloud or escalated or score >= self.score_cloud

        # 5. SPRAWDZENIE DOSTĘPNOŚCI CLOUD
        cloud_ok = self._is_cloud_available()

        if want_cloud and cloud_ok:
            if escalated:
                reason = (
                    f"eskalacja: verifier zawiódł {ctx.verifier_fails}x "
                    f"(próg: {self.verifier_fails_escalate})"
                )
            elif ctx.force_cloud:
                reason = "force-cloud: wymuszony przez context.force_cloud"
            else:
                reason = f"złożoność: score={score} >= próg={self.score_cloud}"

            decision = RouterDecision(
                backend="cloud",
                model=self.cloud_model,
                provider=self.cloud_provider,
                reason=reason,
                complexity_score=score,
                escalated=escalated,
                cloud_available=True,
            )
        else:
            if want_cloud and not cloud_ok:
                reason = (
                    f"local-only: cloud pożądany (score={score}) ale BRAK {self._api_key_env}"
                )
            elif score < self.score_cloud:
                reason = f"lokalny: score={score} < próg={self.score_cloud}"
            else:
                reason = "lokalny: domyślnie"

            # Szybkie proste zadania → fast model
            model = self.local_fast_model if score <= 2 else self.local_model
            decision = RouterDecision(
                backend="local",
                model=model,
                provider="ollama",
                reason=reason,
                complexity_score=score,
                cloud_available=cloud_ok,
            )

        self._log_and_record(ctx, decision)
        return decision

    def record_verifier_result(self, session_id: str, step_id: int, passed: bool) -> None:
        """Rejestruje wynik verifier — używane przez orchestrator do eskalacji."""
        logger.debug(f"[router] session={session_id} step={step_id} verifier={'PASS' if passed else 'FAIL'}")

    def get_report(self) -> str:
        """Generuje raport końcowy: które kroki poszły gdzie."""
        if not self._decisions:
            return "[ROUTER] Brak zarejestrowanych decyzji w tej sesji."

        lines = ["", "╔═══════════════════════════════════════════════════════╗",
                 "║          ROUTER — Raport decyzji sesji                ║",
                 "╚═══════════════════════════════════════════════════════╝"]

        local_count = sum(1 for _, d in self._decisions if d.backend == "local")
        cloud_count = sum(1 for _, d in self._decisions if d.backend == "cloud")
        escalated_count = sum(1 for _, d in self._decisions if d.escalated)
        privacy_count = sum(1 for _, d in self._decisions if d.privacy_protected)

        for i, (ctx, dec) in enumerate(self._decisions, 1):
            step_label = f"Krok {ctx.step_id}" if ctx.step_id is not None else f"Decyzja {i}"
            title = f" ({ctx.step_title})" if ctx.step_title else ""
            lines.append(f"\n  {step_label}{title}:")
            lines.append(f"    Backend : {'☁️  CLOUD' if dec.backend == 'cloud' else '🏠 LOCAL'}")
            lines.append(f"    Model   : {dec.model}")
            lines.append(f"    Powód   : {dec.reason}")
            if dec.privacy_protected:
                lines.append("    ⚠️  PRIVACY PROTECTED — dane wrażliwe, zawsze local")
            if dec.escalated:
                lines.append("    ⬆️  ESCALATED — verifier zawiódł zbyt wiele razy")

        lines.append("\n  ─────────────────────────────────────────────────────")
        lines.append(f"  Podsumowanie: LOCAL={local_count}  CLOUD={cloud_count}  "
                     f"eskalacje={escalated_count}  privacy-protected={privacy_count}")
        lines.append("")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset historii decyzji (nowa sesja)."""
        self._decisions.clear()
        self._cloud_available = None  # re-check przy następnym wywołaniu

    # ── PRIVATE ────────────────────────────────────────────────────────────

    def _detect_sensitive(self, task_lower: str) -> str:
        """Zwraca pierwsze znalezione wrażliwe słowo, lub '' jeśli brak."""
        for kw in self._sensitive_kw:
            if kw in task_lower:
                return kw
        return ""

    def _complexity_score(self, task: str, ctx: RouterContext) -> int:
        """Oblicza wynik złożoności 0–max_score."""
        task_lower = task.lower()
        score = 0

        # Długość zadania
        if len(task) > self.task_length_complex:
            score += 1
        if len(task) > self.task_length_complex * 2:
            score += 1

        # Liczba kroków plannera
        if ctx.plan_steps_total >= self.steps_complex:
            score += 3
        elif ctx.plan_steps_total >= 2:
            score += 1

        # Słowa wysokiej złożoności — +1 za każde trafienie, max 5 punktów
        hits = sum(1 for kw in self._high_kw if kw in task_lower)
        score += min(hits, 5)

        # Słowa niskiej złożoności — -1 za grupę trafień, max -2
        low_hits = sum(1 for kw in self._low_kw if kw in task_lower)
        score -= min(low_hits, 2)

        return max(0, min(score, self.max_score))

    def _is_cloud_available(self) -> bool:
        """Sprawdza czy klucz cloud API jest dostępny (wynik cache'owany per sesję)."""
        if self._cloud_available is None:
            key = os.getenv(self._api_key_env, "").strip()
            self._cloud_available = bool(key)
            if not self._cloud_available:
                logger.warning(
                    f"[router] LOCAL-ONLY MODE: zmienna {self._api_key_env} nie jest ustawiona. "
                    "Ustaw ją aby włączyć cloud fallback."
                )
            else:
                logger.info(f"[router] Cloud API dostępne ({self.cloud_provider})")
        return self._cloud_available

    def _log_and_record(self, ctx: RouterContext, decision: RouterDecision) -> None:
        logger.info(f"[router] {decision.summary()}")
        self._decisions.append((ctx, decision))


# ── SINGLETON per-process ──────────────────────────────────────────────────────

_default_router: Optional[HybridRouter] = None


def get_router() -> HybridRouter:
    """Globalny singleton routera (lazy init)."""
    global _default_router
    if _default_router is None:
        _default_router = HybridRouter()
    return _default_router


def reset_router() -> None:
    """Reset singletona — używaj w testach."""
    global _default_router
    _default_router = None


def choose_model(task: str, context: Optional[RouterContext] = None) -> RouterDecision:
    """Shorthand — używa globalnego singletona routera."""
    return get_router().choose_model(task, context)
