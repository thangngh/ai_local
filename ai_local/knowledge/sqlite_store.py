import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional


def _content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _normalized_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


@dataclass
class KnowledgeEntry:
    id: int
    kind: str
    title: str
    content: str
    source_path: Optional[str]
    tags_json: str
    content_hash: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


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
                    title TEXT NOT NULL DEFAULT 'note',
                    content TEXT NOT NULL,
                    source_path TEXT,
                    tags_json TEXT,
                    content_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # Add content_hash column to existing tables (migration)
            try:
                conn.execute("ALTER TABLE knowledge ADD COLUMN content_hash TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

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
                INSERT INTO knowledge (kind, title, content, source_path, tags_json, content_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("file", title, content, str(path), tags_json, _content_hash(_normalized_text(content)), now, now),
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

        # Duplicate check: prevent same content being inserted twice
        with self._connect() as conn:
            # Use content hash for reliable dedup
            content_hash = _content_hash(_normalized_text(text))
            cursor = conn.execute(
                """
                SELECT id FROM knowledge WHERE content_hash = ? AND kind = 'note'
                """,
                (content_hash,),
            )
            existing = cursor.fetchone()
            if existing:
                raise RuntimeError(
                    f"Knowledge note with same content already exists (id={existing['id']})"
                )

            # Insert new note
            cursor = conn.execute(
                """
                INSERT INTO knowledge (kind, title, content, source_path, tags_json, content_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("note", title, text, None, tags_json, content_hash, now, now),
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
        """Search knowledge with relevance ranking.

        Returns results sorted by relevance score (higher = more relevant).
        """
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
            entries = [KnowledgeEntry(**dict(r)) for r in rows]

            # Rank by relevance in Python: tag match > title match > content match > file kind
            def _rank(entry: KnowledgeEntry) -> tuple:
                q_lower = query.lower()
                score = 0
                if entry.tags_json and q_lower in entry.tags_json.lower():
                    score = 3
                elif entry.title and q_lower in entry.title.lower():
                    score = 2
                # Check word-level match
                for w in words:
                    w_lower = w.lower()
                    if entry.tags_json and w_lower in entry.tags_json.lower():
                        score = max(score, 3)
                    elif entry.title and w_lower in entry.title.lower():
                        score = max(score, 2)
                    elif entry.content and w_lower in entry.content.lower():
                        score = max(score, 1)
                # Penalize 'file' kind vs 'note' kind
                kind_penalty = 1 if entry.kind == 'file' else 0
                return (-score, kind_penalty, entry.id)

            entries.sort(key=_rank)
            return entries

    def remove(self, entry_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM knowledge WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_duplicates(self) -> list[int]:
        """Remove duplicate rows by normalized content hash, keeping the oldest row."""
        self.initialize()
        removed: list[int] = []
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM knowledge ORDER BY id").fetchall()
            seen: set[tuple[str, str]] = set()
            for row in rows:
                content_hash = row["content_hash"] or _content_hash(_normalized_text(str(row["content"])))
                key = (str(row["kind"]), str(content_hash))
                row_id = int(row["id"])
                if key in seen:
                    removed.append(row_id)
                    continue
                seen.add(key)
                if row["content_hash"] != content_hash:
                    conn.execute("UPDATE knowledge SET content_hash = ? WHERE id = ?", (content_hash, row_id))
            if removed:
                conn.executemany("DELETE FROM knowledge WHERE id = ?", [(entry_id,) for entry_id in removed])
            conn.commit()
        return removed

    def stats(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT kind, COUNT(*) AS count FROM knowledge GROUP BY kind ORDER BY kind"
            ).fetchall()
        stats = {"total": 0}
        for row in rows:
            count = int(row["count"])
            stats[str(row["kind"])] = count
            stats["total"] += count
        return stats
