"""
memory2/episodic.py — pamięć epizodyczna: zdarzenia i przebiegi zadań.

Przechowuje co się wydarzyło: kiedy, jaki task, wynik, ile rund, czas.
Backend: SQLite (dane mają strukturę czasową — relacyjny model naturalny).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

_DB_PATH = Path.home() / ".qwen_agent" / "memory2_episodic.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class EpisodicMemory:
    """
    Pamięć epizodyczna — logi przebiegów zadań z kontekstem.
    Każdy wpis: task_id, treść zdarzenia, wynik, meta (czas, backend, rundy).
    """

    def __init__(self):
        self._conn = sqlite3.connect(str(_DB_PATH))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                outcome TEXT DEFAULT 'unknown',
                tags TEXT DEFAULT '[]',
                meta TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            )""")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_task ON episodes(task_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outcome ON episodes(outcome)")
        self._conn.commit()

    def remember(self, content: str, tags: list[str] | None = None,
                 meta: dict | None = None) -> int:
        """
        Zapisz zdarzenie.
        meta może zawierać: task_id, outcome, backend, rounds, duration_s, model
        """
        meta = meta or {}
        task_id = meta.pop("task_id", "")
        outcome = meta.pop("outcome", "unknown")
        ts = datetime.now().isoformat()
        cur = self._conn.execute(
            "INSERT INTO episodes (task_id,content,outcome,tags,meta,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (task_id, content, outcome,
             json.dumps(tags or []), json.dumps(meta), ts))
        self._conn.commit()
        return cur.lastrowid

    def recall(self, query: str, top_k: int = 5,
               tags: list[str] | None = None) -> list[dict]:
        """
        Proste wyszukiwanie tekstowe (LIKE) — epizodyczne nie potrzebuje wektorów,
        liczy się czas i outcome, nie semantyczne podobieństwo.
        """
        words = [w.strip() for w in query.split() if len(w.strip()) > 2]
        if not words:
            rows = self._conn.execute(
                "SELECT id,task_id,content,outcome,tags,meta,created_at "
                "FROM episodes ORDER BY created_at DESC LIMIT ?", (top_k,)
            ).fetchall()
        else:
            like_clause = " OR ".join("content LIKE ?" for _ in words)
            params = [f"%{w}%" for w in words] + [top_k * 3]
            rows = self._conn.execute(
                f"SELECT id,task_id,content,outcome,tags,meta,created_at "
                f"FROM episodes WHERE {like_clause} "
                f"ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        results = []
        for row in rows:
            rid, task_id, content, outcome, tags_j, meta_j, ts = row
            item = {
                "id": rid,
                "task_id": task_id,
                "content": content,
                "outcome": outcome,
                "tags": json.loads(tags_j),
                "meta": json.loads(meta_j),
                "created_at": ts,
                "score": 1.0,
            }
            if tags and not any(t in item["tags"] for t in tags):
                continue
            results.append(item)
        return results[:top_k]

    def get_task_history(self, task_id: str) -> list[dict]:
        """Pobierz pełną historię zadania wg task_id."""
        rows = self._conn.execute(
            "SELECT id,task_id,content,outcome,tags,meta,created_at "
            "FROM episodes WHERE task_id=? ORDER BY created_at ASC",
            (task_id,),
        ).fetchall()
        return [
            {"id": r[0], "task_id": r[1], "content": r[2], "outcome": r[3],
             "tags": json.loads(r[4]), "meta": json.loads(r[5]), "created_at": r[6]}
            for r in rows
        ]

    def forget(self, mem_id: int) -> bool:
        self._conn.execute("DELETE FROM episodes WHERE id=?", (mem_id,))
        self._conn.commit()
        return True

    def stats(self) -> dict:
        total = self._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        outcomes = dict(self._conn.execute(
            "SELECT outcome, COUNT(*) FROM episodes GROUP BY outcome"
        ).fetchall())
        return {"total": total, "outcomes": outcomes}
