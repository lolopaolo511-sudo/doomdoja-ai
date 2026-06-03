"""
memory2/memory2.py — zunifikowane API dla 3 typów pamięci.

Użycie:
    from memory2 import Memory2, MemoryType

    mem = Memory2()
    mem.remember("semantic", "Python dict lookup jest O(1)", tags=["python"])
    mem.remember("episodic", "Zadanie scraping ukończone", meta={"outcome":"success"})
    mem.remember("procedural", "Jak scrapować tabele: 1.find_table 2.extract_rows",
                 meta={"name": "scrape_table", "steps": ["find_table","extract_rows"]})

    results = mem.recall("jak szybki jest dict?", type="semantic")
    context = mem.recall_context("napisz scraper tabeli")  # wszystkie 3 typy
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from .semantic import SemanticMemory
from .episodic import EpisodicMemory
from .procedural import ProceduralMemory


class MemoryType(str, Enum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


class Memory2:
    """
    Zunifikowany interfejs do 3 typów pamięci.
    Każdy typ jest izolowaną bazą danych — możliwe niezależne użycie.
    """

    def __init__(self):
        self.semantic = SemanticMemory()
        self.episodic = EpisodicMemory()
        self.procedural = ProceduralMemory()

    # ── Zapis ─────────────────────────────────────────────────────────────────

    def remember(
        self,
        type: str | MemoryType,
        content: str,
        tags: list[str] | None = None,
        meta: dict | None = None,
    ) -> int:
        """
        Zapisz wspomnienie.

        Args:
            type: "semantic" | "episodic" | "procedural"
            content: treść wspomnienia
            tags: lista tagów (opcjonalne)
            meta: dodatkowe metadane specyficzne dla typu:
              semantic:    brak wymaganych
              episodic:    task_id, outcome ("success"|"fail"|"error")
              procedural:  name, steps (list[str]), outcome
        Returns:
            ID wpisu
        """
        t = MemoryType(type)
        if t == MemoryType.SEMANTIC:
            return self.semantic.remember(content, tags=tags, meta=meta)
        elif t == MemoryType.EPISODIC:
            return self.episodic.remember(content, tags=tags, meta=meta)
        elif t == MemoryType.PROCEDURAL:
            return self.procedural.remember(content, tags=tags, meta=meta)
        raise ValueError(f"Nieznany typ pamięci: {type}")

    # ── Odczyt ────────────────────────────────────────────────────────────────

    def recall(
        self,
        query: str,
        type: str | MemoryType | None = None,
        top_k: int = 5,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """
        Znajdź pasujące wspomnienia.

        Args:
            query: zapytanie (tekst naturalny)
            type: opcjonalnie ogranicz do jednego typu; None = wszystkie 3
            top_k: maksymalna liczba wyników PER TYP (lub łącznie gdy type=None)
            tags: opcjonalny filtr tagów
        Returns:
            Lista wyników z polem "memory_type" i "score".
        """
        t = MemoryType(type) if type else None

        if t == MemoryType.SEMANTIC:
            hits = self.semantic.recall(query, top_k=top_k, tags=tags)
            return _tag_type(hits, "semantic")
        if t == MemoryType.EPISODIC:
            hits = self.episodic.recall(query, top_k=top_k, tags=tags)
            return _tag_type(hits, "episodic")
        if t == MemoryType.PROCEDURAL:
            hits = self.procedural.recall(query, top_k=top_k, tags=tags)
            return _tag_type(hits, "procedural")

        # Wszystkie 3 typy — zbierz, posortuj po score, ogranicz
        k_each = max(2, top_k // 2)
        all_hits = (
            _tag_type(self.semantic.recall(query, top_k=k_each, tags=tags), "semantic")
            + _tag_type(self.episodic.recall(query, top_k=k_each, tags=tags), "episodic")
            + _tag_type(self.procedural.recall(query, top_k=k_each, tags=tags), "procedural")
        )
        all_hits.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_hits[:top_k]

    def recall_context(self, task: str, top_k: int = 6) -> str:
        """
        Auto-przywoływanie kontekstu przy starcie zadania.
        Zwraca gotowy string do wklejenia do promptu agenta.
        """
        hits = self.recall(task, top_k=top_k)
        if not hits:
            return ""
        lines = ["=== Kontekst z pamięci ==="]
        for h in hits:
            mt = h.get("memory_type", "?")
            content = h.get("content", "")[:200]
            score = h.get("score", 0)
            lines.append(f"[{mt.upper()}] (score={score:.2f}) {content}")
        lines.append("=========================")
        return "\n".join(lines)

    # ── Usuwanie ──────────────────────────────────────────────────────────────

    def forget(self, type: str | MemoryType, mem_id: int) -> bool:
        t = MemoryType(type)
        if t == MemoryType.SEMANTIC:
            return self.semantic.forget(mem_id)
        if t == MemoryType.EPISODIC:
            return self.episodic.forget(mem_id)
        if t == MemoryType.PROCEDURAL:
            return self.procedural.forget(mem_id)
        return False

    # ── Info ─────────────────────────────────────────────────────────────────

    def status(self) -> dict:
        ep_stats = self.episodic.stats()
        return {
            "semantic_backend": self.semantic.backend,
            "episodic_total": ep_stats["total"],
            "episodic_outcomes": ep_stats["outcomes"],
        }


def _tag_type(hits: list[dict], memory_type: str) -> list[dict]:
    for h in hits:
        h["memory_type"] = memory_type
    return hits
