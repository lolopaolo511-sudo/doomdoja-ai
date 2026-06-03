"""
workflow/budget.py — Twardy budżet tokenów dla workflow i per-agent.

Użycie:
    budget = WorkflowBudget(total=10000)
    sub = budget.child(2000)   # per-agent limit
    sub.charge(500)            # zużycie (przybliżone: chars//4)
    print(budget.report())
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional


class TokenBudgetExceeded(Exception):
    """Twardy limit tokenów przekroczony — agent zatrzymany."""

    def __init__(self, message: str, used: int = 0, limit: int = 0):
        super().__init__(message)
        self.used = used
        self.limit = limit


def estimate_tokens(text: str) -> int:
    """Przybliżona liczba tokenów: ~4 znaki = 1 token."""
    return max(1, len(text) // 4)


@dataclass
class WorkflowBudget:
    """
    Hierarchiczny budżet tokenów — workflow-level + per-agent sub-budgets.
    Thread-safe (blokada dla parallel() agentów).
    """
    total: int
    _used: int = field(default=0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _children: list["WorkflowBudget"] = field(default_factory=list, init=False, repr=False)
    label: str = "workflow"

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.total - self._used)

    def child(self, limit: int, label: str = "agent") -> "WorkflowBudget":
        """Tworzy sub-budżet dla jednego agenta — max `limit` tokenów."""
        sub = WorkflowBudget(total=limit, label=label)
        with self._lock:
            self._children.append(sub)
        return sub

    def check(self, estimated: int) -> None:
        """Sprawdź czy jest miejsce — rzuć wyjątek jeśli nie."""
        with self._lock:
            if self._used + estimated > self.total:
                raise TokenBudgetExceeded(
                    f"[{self.label}] Budżet tokenów przekroczony: "
                    f"{self._used + estimated} > {self.total} (remaining={self.remaining})",
                    used=self._used + estimated,
                    limit=self.total,
                )

    def charge(self, tokens: int) -> None:
        """Zarejestruj zużycie. Rzuć wyjątek jeśli przekroczony po fakcie."""
        with self._lock:
            self._used += tokens
            if self._used > self.total:
                raise TokenBudgetExceeded(
                    f"[{self.label}] Budżet przekroczony po wykonaniu: "
                    f"{self._used} > {self.total}",
                    used=self._used,
                    limit=self.total,
                )

    def report(self) -> str:
        lines = [f"[{self.label}] {self._used}/{self.total} tokenów "
                 f"({100*self._used//max(1,self.total)}%)"]
        for child in self._children:
            lines.append("  " + child.report())
        return "\n".join(lines)
