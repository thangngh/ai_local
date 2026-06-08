import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class KnowledgeEntry:
    id: int
    kind: str
    title: str
    content: str
    source_path: Optional[str]
    tags_json: str
    created_at: str
    updated_at: str


class SQLiteKnowledgeStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_path TEXT,
                    tags_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_file(self, path: Path, tag: str) -> KnowledgeEntry:
        content = path.read_text(encoding="utf-8")
        title = path.name
        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps([tag])
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO knowledge (kind, title, content, source_path, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("file", title, content, str(path), tags_json, now, now),
            )
            entry_id = cursor.lastrowid
            conn.commit()
            if entry_id is None:
                raise RuntimeError("Failed to insert file knowledge")
            return KnowledgeEntry(
                id=entry_id,
                kind="file",
                title=title,
                content=content,
                source_path=str(path),
                tags_json=tags_json,
                created_at=now,
                updated_at=now,
            )

    def add_note(self, text: str, tag: str | list[str], title: str = "note") -> KnowledgeEntry:
        now = datetime.now(timezone.utc).isoformat()
        if isinstance(tag, str):
            tags_json = json.dumps([tag])
        else:
            tags_json = json.dumps(tag)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO knowledge (kind, title, content, source_path, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("note", title, text, None, tags_json, now, now),
            )
            entry_id = cursor.lastrowid
            conn.commit()
            if entry_id is None:
                raise RuntimeError("Failed to insert note knowledge")
            return KnowledgeEntry(
                id=entry_id,
                kind="note",
                title=title,
                content=text,
                source_path=None,
                tags_json=tags_json,
                created_at=now,
                updated_at=now,
            )

    def list_all(self) -> list[KnowledgeEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM knowledge ORDER BY id").fetchall()
            return [KnowledgeEntry(**dict(r)) for r in rows]

    def search(self, query: str) -> list[KnowledgeEntry]:
        words = [w for w in query.replace("?", "").split() if len(w) > 3 or w.lower() in ("ai",)]
        if not words:
            words = query.split()
            
        conditions = []
        params = []
        for word in words:
            pattern = f"%{word}%"
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([pattern, pattern])
            
        where_clause = " OR ".join(conditions)
        if not where_clause:
            return []
            
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM knowledge WHERE {where_clause} ORDER BY id",
                tuple(params),
            ).fetchall()
            return [KnowledgeEntry(**dict(r)) for r in rows]
