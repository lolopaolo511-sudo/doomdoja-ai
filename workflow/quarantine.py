"""
workflow/quarantine.py — Izolacja agentów czytających niezaufane dane.

Quarantine wymusza, że agent który czyta surowe dane z sieci (scraping, tickety,
ogłoszenia) NIE może wywoływać akcji (zapis pliku, git, webhook, zewnętrzne API).
Akcje wykonują osobne agenty, które NIGDY nie widzą surowych danych.

Egzekucja na poziomie API:
  1. Flaga thread-local _quarantine.active blokuje wywołania @action_tool
  2. AgentResult.quarantined=True oznacza wyjście jako "niezaufane"
  3. assert_clean() blokuje użycie niezaufanego wyniku jako instrukcji akcji

Użycie:
    with quarantine():
        result = agent("Podsumuj te ogłoszenia", context=raw_html)
    # result.quarantined == True
    # Przekaż TYLKO result.output (tekst) do następnego agenta — nie raw_html

    @action_tool
    def write_report(path, content): ...
    # Rzuci QuarantineViolation jeśli wywołane w kontekście quarantine()
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
R = TypeVar("R")

_quarantine = threading.local()


class QuarantineViolation(Exception):
    """Próba wywołania akcji w trybie kwarantanny."""
    pass


def is_quarantined() -> bool:
    """Czy bieżący wątek jest w trybie kwarantanny?"""
    return getattr(_quarantine, "active", False)


@contextmanager
def quarantine():
    """Context manager — wszystkie agenty wewnątrz są kwarantannowane."""
    prev = getattr(_quarantine, "active", False)
    _quarantine.active = True
    try:
        yield
    finally:
        _quarantine.active = prev


def action_tool(fn: Callable[P, R]) -> Callable[P, R]:
    """
    Dekorator oznaczający funkcję jako narzędzie akcji.
    Rzuca QuarantineViolation jeśli wywołane w trybie kwarantanny.
    """
    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if is_quarantined():
            raise QuarantineViolation(
                f"Akcja '{fn.__name__}' zablokowana w trybie quarantine. "
                "Użyj osobnego agenta bez dostępu do surowych danych."
            )
        return fn(*args, **kwargs)
    return wrapper


def assert_clean(obj: object, *, allow_text_passthrough: bool = True) -> None:
    """
    Sprawdź czy obiekt jest bezpieczny do użycia jako instrukcja akcji.

    Args:
        obj: wynik agenta (AgentResult lub string)
        allow_text_passthrough: jeśli True, surowy tekst (string) jest dozwolony
                                 jako input do następnego agenta (ale nie bezpośrednio
                                 jako instrukcja do akcji — tylko jako context).

    Raises:
        QuarantineViolation: jeśli obiekt pochodzi z kwarantanny i próbuje
                              być użyty bezpośrednio do akcji.
    """
    quarantined_flag = getattr(obj, "quarantined", False)
    if quarantined_flag and not allow_text_passthrough:
        raise QuarantineViolation(
            "Wynik z kwarantanny nie może być użyty bezpośrednio jako instrukcja akcji. "
            "Przekaż przez weryfikator (adversarial_verification) lub czysty agent."
        )
