"""
memory2/procedural.py — pamięć proceduralna: wyuczone procedury i przepisy.

Przechowuje "jak coś zrobić": kroки, przykłady sukcesu/porażki, success_rate.
Każda procedura ma nazwę, listę kroków i statystyki skuteczności.
Backend: SQLite.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

_DB_PATH = Path.home() / ".qwen_agent" / "memory2_procedural.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class ProceduralMemory:
    """
    Pamięć proceduralna — przepisy na działania.
    Każdy wpis: nazwa procedury, kroki, przykłady (co działało/nie działało),
    success_rate aktualizowany przy każdym run.
    """

    def __init__(self):
        self._conn = sqlite3.connect(str(_DB_PATH))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                steps TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                runs_total INTEGER DEFAULT 0,
                runs_success INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_name ON procedures(name)")
        self._conn.commit()

    def remember(self, content: str, tags: list[str] | None = None,
                 meta: dict | None = None) -> int:
        """
        Zapisz lub zaktualizuj procedurę.
        meta może zawierać:
          name (str)       — nazwa procedury (domyślnie: pierwsze 60 znaków content)
          steps (list)     — lista kroków ["krok1", "krok2"]
          outcome (str)    — "success" | "fail" — aktualizuje statystyki
        """
        meta = meta or {}
        name = meta.get("name") or content[:60].replace("\n", " ")
        steps = meta.get("steps", [])
        outcome = meta.get("outcome", "")
        ts = datetime.now().isoformat()

        # Sprawdź czy procedura o tej nazwie już istnieje
        existing = self._conn.execute(
            "SELECT id, runs_total, runs_success FROM procedures WHERE name=?",
            (name,),
        ).fetchone()

        if existing:
            rid, runs_total, runs_success = existing
            if outcome == "success":
                runs_total += 1
                runs_success += 1
            elif outcome == "fail":
                runs_total += 1
            new_steps = steps or json.loads(
                self._conn.execute(
                    "SELECT steps FROM procedures WHERE id=?", (rid,)
                ).fetchone()[0]
            )
            self._conn.execute(
                "UPDATE procedures SET content=?,steps=?,tags=?,runs_total=?,"
                "runs_success=?,updated_at=? WHERE id=?",
                (content, json.dumps(new_steps), json.dumps(tags or []),
                 runs_total, runs_success, ts, rid),
            )
            self._conn.commit()
            return rid

        runs_total = 1 if outcome in ("success", "fail") else 0
        runs_success = 1 if outcome == "success" else 0
        cur = self._conn.execute(
            "INSERT INTO procedures "
            "(name,content,steps,tags,runs_total,runs_success,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (name, content, json.dumps(steps), json.dumps(tags or []),
             runs_total, runs_success, ts, ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def recall(self, query: str, top_k: int = 5,
               tags: list[str] | None = None) -> list[dict]:
        """Wyszukaj procedury pasujące do zapytania (tekstowo + nazwa)."""
        words = [w.strip() for w in query.split() if len(w.strip()) > 2]
        if not words:
            rows = self._conn.execute(
                "SELECT id,name,content,steps,tags,runs_total,runs_success,updated_at "
                "FROM procedures ORDER BY runs_success DESC LIMIT ?", (top_k,)
            ).fetchall()
        else:
            like_clause = " OR ".join(
                "(content LIKE ? OR name LIKE ?)" for _ in words)
            params = []
            for w in words:
                params += [f"%{w}%", f"%{w}%"]
            params.append(top_k * 3)
            rows = self._conn.execute(
                f"SELECT id,name,content,steps,tags,runs_total,runs_success,updated_at "
                f"FROM procedures WHERE {like_clause} "
                f"ORDER BY runs_success DESC LIMIT ?",
                params,
            ).fetchall()

        results = []
        for row in rows:
            rid, name, content, steps_j, tags_j, rt, rs, ts = row
            success_rate = rs / rt if rt > 0 else None
            item = {
                "id": rid,
                "name": name,
                "content": content,
                "steps": json.loads(steps_j),
                "tags": json.loads(tags_j),
                "runs_total": rt,
                "runs_success": rs,
                "success_rate": success_rate,
                "updated_at": ts,
                "score": success_rate or 0.5,
            }
            if tags and not any(t in item["tags"] for t in tags):
                continue
            results.append(item)
        return results[:top_k]

    def forget(self, mem_id: int) -> bool:
        self._conn.execute("DELETE FROM procedures WHERE id=?", (mem_id,))
        self._conn.commit()
        return True

    def record_run(self, name: str, success: bool) -> None:
        """Szybka aktualizacja statystyk bez zmiany treści."""
        existing = self._conn.execute(
            "SELECT id FROM procedures WHERE name=?", (name,)).fetchone()
        if not existing:
            self.remember(f"Procedura: {name}", meta={
                "name": name, "outcome": "success" if success else "fail"})
            return
        rid = existing[0]
        self._conn.execute(
            "UPDATE procedures SET runs_total=runs_total+1, "
            "runs_success=runs_success+?, updated_at=? WHERE id=?",
            (1 if success else 0, datetime.now().isoformat(), rid),
        )
        self._conn.commit()
