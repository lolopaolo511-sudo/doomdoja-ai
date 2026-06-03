"""
router/calibration.py — kalibracja progów routera na podstawie historii decyzji.

Algorytm:
  1. Wczytaj statystyki skuteczności z feedback.py
  2. Dla każdej klasy zadań porównaj local vs cloud
  3. Jeśli local radzi sobie dobrze (rate > MIN_LOCAL_RATE) → obniż próg eskalacji
  4. Jeśli cloud nie poprawia wyników nad local → nie eskaluj dla tej klasy
  5. Zwróć skorygowane progi (NIE nadpisuj config.yaml — tylko session overrides)

Minimalne dane do kalibracji: MIN_SAMPLES decyzji per (backend, task_class).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("qwen_agent.router.calibration")

# Progi domyślne (z config.yaml — tu jako fallback)
DEFAULT_COMPLEXITY_THRESHOLD = 6
DEFAULT_VERIFIER_ESCALATE = 2

# Parametry kalibracji
MIN_SAMPLES = 3          # min. N decyzji żeby opłacało się kalibrować
MIN_LOCAL_RATE = 0.80    # local radzi sobie dobrze powyżej tej wartości
CLOUD_UPLIFT_MIN = 0.05  # cloud musi poprawiać o min. 5pp żeby eskalacja była sens


@dataclass
class CalibrationResult:
    """Wynik kalibracji progów routera."""
    complexity_threshold: int = DEFAULT_COMPLEXITY_THRESHOLD
    verifier_escalate: int = DEFAULT_VERIFIER_ESCALATE
    adjustments: list[str] = field(default_factory=list)  # log zmian
    task_class_overrides: dict[str, str] = field(default_factory=dict)
    # task_class → "force_local" | "allow_cloud" | "no_escalate"

    def describe(self) -> str:
        lines = [
            f"Próg złożoności → cloud   : {self.complexity_threshold}",
            f"Eskalacja verifier po N fail: {self.verifier_escalate}",
        ]
        if self.adjustments:
            lines.append("Zmiany:")
            lines.extend(f"  • {a}" for a in self.adjustments)
        if self.task_class_overrides:
            lines.append("Nadpisania per klasa:")
            for cls, action in self.task_class_overrides.items():
                lines.append(f"  • {cls} → {action}")
        return "\n".join(lines)


def calibrate(stats: dict) -> CalibrationResult:
    """
    Na podstawie statystyk (z RouterFeedback.get_stats()) oblicz skalibrowane progi.

    Args:
        stats: {"local": {"simple": {"total":N, "rate":0.9, ...}, ...}, "cloud": {...}}
    Returns:
        CalibrationResult z opcjonalnie zmienionymi progami
    """
    result = CalibrationResult()

    local_stats = stats.get("local", {})
    cloud_stats = stats.get("cloud", {})

    # Zbierz wszystkie klasy zadań
    all_classes = set(local_stats) | set(cloud_stats)

    for task_class in all_classes:
        local = local_stats.get(task_class)
        cloud = cloud_stats.get(task_class)

        # Pomiń jeśli za mało danych
        local_ok = local and local.get("total", 0) >= MIN_SAMPLES
        cloud_ok = cloud and cloud.get("total", 0) >= MIN_SAMPLES

        if not local_ok and not cloud_ok:
            continue

        local_rate = local.get("rate") if local_ok else None
        cloud_rate = cloud.get("rate") if cloud_ok else None

        # Reguła 1: local radzi sobie świetnie → nie eskaluj tej klasy
        if local_ok and local_rate is not None and local_rate >= MIN_LOCAL_RATE:
            result.task_class_overrides[task_class] = "force_local"
            result.adjustments.append(
                f"{task_class}: local rate={local_rate:.0%} ≥ {MIN_LOCAL_RATE:.0%} "
                f"→ force_local (brak eskalacji)"
            )
            # Obniż globalny próg złożoności jeśli dotyczy klasy simple/medium
            if task_class in ("simple", "medium"):
                new_t = min(result.complexity_threshold + 1, 9)
                if new_t != result.complexity_threshold:
                    result.complexity_threshold = new_t
                    result.adjustments.append(
                        f"Próg złożoności +1 → {new_t} "
                        f"(local radzi sobie z {task_class})"
                    )
            continue

        # Reguła 2: cloud jest dostępny ale nie daje uplift → brak eskalacji
        if local_ok and cloud_ok and local_rate is not None and cloud_rate is not None:
            uplift = cloud_rate - local_rate
            if uplift < CLOUD_UPLIFT_MIN:
                result.task_class_overrides[task_class] = "no_escalate"
                result.adjustments.append(
                    f"{task_class}: cloud uplift={uplift:+.1%} < {CLOUD_UPLIFT_MIN:.0%} "
                    f"→ no_escalate (cloud nie pomaga)"
                )
                continue

        # Reguła 3: local często failuje (< 0.4) i cloud pomaga → obniż próg eskalacji
        if local_ok and local_rate is not None and local_rate < 0.40:
            new_v = max(1, result.verifier_escalate - 1)
            if new_v != result.verifier_escalate:
                result.verifier_escalate = new_v
                result.adjustments.append(
                    f"{task_class}: local rate={local_rate:.0%} < 40% "
                    f"→ verifier_escalate obniżony do {new_v}"
                )

    if not result.adjustments:
        result.adjustments.append(
            "Brak zmian — dane historyczne nie przekraczają progów kalibracji "
            f"(min {MIN_SAMPLES} próbek per klasa)"
        )

    return result


def should_escalate(task_class: str, verifier_fails: int,
                    calibration: CalibrationResult) -> bool:
    """
    Sprawdź czy router powinien eskalować zadanie do cloud.
    Uwzględnia kalibrację: force_local i no_escalate blokują eskalację.
    """
    override = calibration.task_class_overrides.get(task_class)
    if override in ("force_local", "no_escalate"):
        return False
    return verifier_fails >= calibration.verifier_escalate
