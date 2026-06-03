#!/usr/bin/env python3
"""
Trwała pamięć agenta między sesjami.
Przechowuje fakty, decyzje i wyniki w SQLite + wektory embeddingów przez Ollama.

Użycie:
  from memory import AgentMemory
  mem = AgentMemory()
  mem.remember("Użytkownik preferuje Python 3.12")
  mem.remember("Repo /tmp/myapp używa pytest", tags=["repo:/tmp/myapp"])
  context = mem.recall("jaki framework testów?")
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from qwen_agent.core import get_config, get_llm_client
except ModuleNotFoundError:
    # Allow running as script from inside qwen-agent/ without installation
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from core import get_config, get_llm_client

cfg = get_config()
DEFAULT_DB = cfg.memory_db_path
SIMILARITY_THRESHOLD = 0.75  # cosine distance (niższe = bardziej podobne)


def _embed(text: str) -> list[float]:
    """Now uses the hardened central LLM client."""
    llm = get_llm_client()
    return llm.embed(text, model=cfg.embed_model)


def _cosine_dist(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


class AgentMemory:
    def __init__(self, db_path: str = ""):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                embedding TEXT,
                created_at TEXT NOT NULL,
                session_id TEXT DEFAULT '',
                importance INTEGER DEFAULT 1
            )
        """)
        self._conn.commit()

    def remember(
        self,
        content: str,
        tags: Optional[list[str]] = None,
        session_id: str = "",
        importance: int = 1,
    ) -> int:
        """Zapisuje fakt/wynik do pamięci trwałej."""
        emb = _embed(content)
        now = datetime.now().isoformat()
        cur = self._conn.execute(
            """INSERT INTO memories (content, tags, embedding, created_at, session_id, importance)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (content, json.dumps(tags or []), json.dumps(emb), now, session_id, importance),
        )
        self._conn.commit()
        return cur.lastrowid

    def recall(
        self,
        query: str,
        top_k: int = 5,
        tags: Optional[list[str]] = None,
        max_age_days: Optional[int] = None,
    ) -> list[dict]:
        """Przywołuje najistotniejsze wspomnienia dla danego zapytania."""
        query_emb = _embed(query)

        where_clauses = []
        params: list = []

        if tags:
            # proste AND-matching na json tags
            for tag in tags:
                where_clauses.append("tags LIKE ?")
                params.append(f"%{tag}%")

        if max_age_days:
            cutoff = datetime.now().replace(
                hour=0, minute=0, second=0
            )
            from datetime import timedelta
            cutoff -= timedelta(days=max_age_days)
            where_clauses.append("created_at >= ?")
            params.append(cutoff.isoformat())

        sql = "SELECT id, content, tags, embedding, created_at, session_id, importance FROM memories"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        rows = self._conn.execute(sql, params).fetchall()
        scored = []
        for row in rows:
            rid, content, tags_json, emb_json, created_at, session_id, importance = row
            if emb_json:
                emb = json.loads(emb_json)
                dist = _cosine_dist(query_emb, emb)
                scored.append({
                    "id": rid,
                    "content": content,
                    "tags": json.loads(tags_json),
                    "created_at": created_at,
                    "session_id": session_id,
                    "importance": importance,
                    "distance": dist,
                })

        scored.sort(key=lambda x: x["distance"])
        return [m for m in scored[:top_k] if m["distance"] < SIMILARITY_THRESHOLD]

    def recall_all(self, limit: int = 50) -> list[dict]:
        """Zwraca ostatnie wspomnienia."""
        rows = self._conn.execute(
            "SELECT id, content, tags, created_at, session_id, importance "
            "FROM memories ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"id": r[0], "content": r[1], "tags": json.loads(r[2]),
             "created_at": r[3], "session_id": r[4], "importance": r[5]}
            for r in rows
        ]

    def forget(self, memory_id: int):
        """Usuwa wspomnienie po ID."""
        self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()

    def format_for_prompt(self, memories: list[dict]) -> str:
        """Formatuje wspomnienia jako blok kontekstu do promptu."""
        if not memories:
            return ""
        lines = ["=== PAMIĘĆ AGENTA (poprzednie sesje) ==="]
        for m in memories:
            ts = m["created_at"][:16].replace("T", " ")
            tags = f" [{', '.join(m['tags'])}]" if m["tags"] else ""
            lines.append(f"[{ts}{tags}] {m['content']}")
        lines.append("=========================================")
        return "\n".join(lines)

    def stats(self) -> dict:
        count = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        oldest = self._conn.execute("SELECT MIN(created_at) FROM memories").fetchone()[0]
        newest = self._conn.execute("SELECT MAX(created_at) FROM memories").fetchone()[0]
        return {"total": count, "oldest": oldest, "newest": newest, "db": str(self.db_path)}

    def close(self):
        self._conn.close()
