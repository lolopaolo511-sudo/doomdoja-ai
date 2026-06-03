"""
memory2/semantic.py — pamięć semantyczna: fakty i wiedza jako wektory.

Backend: Qdrant (REST API przez httpx) z fallbackiem na SQLite + cosine sim.
Embedding: nomic-embed-text przez lokalną Ollama (768 wymiarów).

Kolekcja Qdrant: "agent_semantic" (tworzona automatycznie przy pierwszym zapisie).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

_QDRANT_URL = "http://localhost:6333"
_COLLECTION = "agent_semantic"
_DIM = 768
_DB_PATH = Path.home() / ".qwen_agent" / "memory2_semantic.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _embed(text: str) -> list[float]:
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core import get_llm_client
        return get_llm_client().embed(text)
    except Exception:
        # Zero-vector fallback (semantics degraded but won't crash)
        return [0.0] * _DIM


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── Qdrant REST helpers ───────────────────────────────────────────────────────

def _qdrant_alive() -> bool:
    try:
        r = httpx.get(f"{_QDRANT_URL}/readyz", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _ensure_collection() -> None:
    r = httpx.get(f"{_QDRANT_URL}/collections/{_COLLECTION}", timeout=5.0)
    if r.status_code == 404:
        httpx.put(
            f"{_QDRANT_URL}/collections/{_COLLECTION}",
            json={"vectors": {"size": _DIM, "distance": "Cosine"}},
            timeout=10.0,
        ).raise_for_status()


def _qdrant_upsert(point_id: int, vector: list[float], payload: dict) -> None:
    _ensure_collection()
    httpx.put(
        f"{_QDRANT_URL}/collections/{_COLLECTION}/points",
        json={"points": [{"id": point_id, "vector": vector, "payload": payload}]},
        timeout=15.0,
    ).raise_for_status()


def _qdrant_search(vector: list[float], top_k: int) -> list[dict]:
    _ensure_collection()
    r = httpx.post(
        f"{_QDRANT_URL}/collections/{_COLLECTION}/points/search",
        json={"vector": vector, "limit": top_k, "with_payload": True},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json().get("result", [])


def _qdrant_delete(point_id: int) -> None:
    httpx.post(
        f"{_QDRANT_URL}/collections/{_COLLECTION}/points/delete",
        json={"points": [point_id]},
        timeout=10.0,
    )


# ── SQLite fallback ────────────────────────────────────────────────────────────

class _SQLiteSemantic:
    def __init__(self):
        self._conn = sqlite3.connect(str(_DB_PATH))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                vector TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
        self._conn.commit()

    def upsert(self, row_id: Optional[int], content: str, tags: list[str],
               vector: list[float]) -> int:
        ts = datetime.now().isoformat()
        if row_id:
            self._conn.execute(
                "UPDATE semantic SET content=?, tags=?, vector=?, created_at=? WHERE id=?",
                (content, json.dumps(tags), json.dumps(vector), ts, row_id))
            self._conn.commit()
            return row_id
        cur = self._conn.execute(
            "INSERT INTO semantic (content,tags,vector,created_at) VALUES (?,?,?,?)",
            (content, json.dumps(tags), json.dumps(vector), ts))
        self._conn.commit()
        return cur.lastrowid

    def search(self, query_vec: list[float], top_k: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, content, tags, vector, created_at FROM semantic").fetchall()
        scored = []
        for rid, content, tags, vec_json, ts in rows:
            vec = json.loads(vec_json)
            sim = _cosine_sim(query_vec, vec)
            scored.append({"id": rid, "score": sim, "content": content,
                           "tags": json.loads(tags), "created_at": ts})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete(self, row_id: int) -> None:
        self._conn.execute("DELETE FROM semantic WHERE id=?", (row_id,))
        self._conn.commit()


# ── Public API ─────────────────────────────────────────────────────────────────

class SemanticMemory:
    """
    Pamięć semantyczna — fakty, wiedza.
    Używa Qdrant REST API gdy dostępny, SQLite inaczej.
    """
    def __init__(self):
        self._use_qdrant = _qdrant_alive()
        self._sqlite = _SQLiteSemantic()
        if self._use_qdrant:
            try:
                _ensure_collection()
            except Exception:
                self._use_qdrant = False

    def remember(self, content: str, tags: list[str] | None = None,
                 meta: dict | None = None) -> int:
        """Zapisz fakt. Zwraca ID wpisu."""
        tags = tags or []
        vector = _embed(content)
        # SQLite jest zawsze source of truth dla ID
        row_id = self._sqlite.upsert(None, content, tags, vector)
        payload = {"content": content, "tags": tags,
                   "created_at": datetime.now().isoformat(), **(meta or {})}
        if self._use_qdrant:
            try:
                _qdrant_upsert(row_id, vector, payload)
            except Exception as e:
                print(f"[semantic] Qdrant upsert warn: {e}")
        return row_id

    def recall(self, query: str, top_k: int = 5,
               tags: list[str] | None = None) -> list[dict]:
        """Zwróć top_k najistotniejszych faktów."""
        qvec = _embed(query)
        if self._use_qdrant:
            try:
                hits = _qdrant_search(qvec, top_k * 2)
                results = []
                for h in hits:
                    p = h.get("payload", {})
                    if tags and not any(t in p.get("tags", []) for t in tags):
                        continue
                    results.append({
                        "id": h["id"],
                        "score": h["score"],
                        "content": p.get("content", ""),
                        "tags": p.get("tags", []),
                        "created_at": p.get("created_at", ""),
                        "source": "qdrant",
                    })
                return results[:top_k]
            except Exception as e:
                print(f"[semantic] Qdrant search warn, fallback SQLite: {e}")
        # SQLite fallback
        hits = self._sqlite.search(qvec, top_k * 2)
        if tags:
            hits = [h for h in hits if any(t in h["tags"] for t in tags)]
        for h in hits:
            h["source"] = "sqlite"
        return hits[:top_k]

    def forget(self, mem_id: int) -> bool:
        self._sqlite.delete(mem_id)
        if self._use_qdrant:
            try:
                _qdrant_delete(mem_id)
            except Exception:
                pass
        return True

    @property
    def backend(self) -> str:
        return "qdrant" if self._use_qdrant else "sqlite"
