"""
workflow/patterns/ — gotowe szablony orkiestracji.

Wzorce:
    classify_and_act          klasyfikacja typu zadania → routing do agenta/modelu
    fan_out_and_synthesize    podział na N niezależnych części → parallel → synteza
    adversarial_verification  niezależny „wrogi" weryfikator bez wiedzy o autorze
    generate_and_filter       generuj N opcji → filtruj rubryką + dedup → top-K
    tournament                parami porównaj → ranking (dla rzeczy „po guście")
    loop_until_done           iteruj aż twardy warunek spełniony (max_iter hard stop)
"""

from .classify_and_act import classify_and_act, ClassifyResult
from .fan_out_and_synthesize import fan_out_and_synthesize, FanOutResult
from .adversarial_verification import adversarial_verification, AdversarialResult, Verdict
from .generate_and_filter import generate_and_filter, FilteredResult
from .tournament import tournament, TournamentResult
from .loop_until_done import loop_until_done, LoopResult

__all__ = [
    "classify_and_act", "ClassifyResult",
    "fan_out_and_synthesize", "FanOutResult",
    "adversarial_verification", "AdversarialResult", "Verdict",
    "generate_and_filter", "FilteredResult",
    "tournament", "TournamentResult",
    "loop_until_done", "LoopResult",
]
