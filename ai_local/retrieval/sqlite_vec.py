from __future__ import annotations

import importlib
import sqlite3
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from ai_local.indexer.models import IndexedChunk
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.retrieval.vector import TextEmbedder


class SqliteVecProvider:
    def __init__(
        self,
        db_path: Path,
        embedder: TextEmbedder,
        *,
        module_loader: Callable[[], ModuleType] | None = None,
    ) -> None:
        self._db_path = db_path
        self._embedder = embedder
        self._module_loader = module_loader or _load_sqlite_vec_module

    @staticmethod
    def is_available() -> bool:
        try:
            _load_sqlite_vec_module()
        except ModuleNotFoundError:
            return False
        return True

    def sync(self, store: KnowledgeIndexStore) -> int:
        self.initialize()
        indexed = 0
        chunks = store.all_chunks()
        with self._connect() as connection:
            self._delete_removed_embeddings(connection, chunks)
            for chunk in chunks:
                indexed += self._sync_chunk(connection, chunk)
        return indexed

    def search(self, query: str, *, limit: int) -> list[IndexedChunk]:
        self.initialize()
        vector = self._serialize(self._embedder.embed(query))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk.*, vec.distance
                FROM vec_chunk_embeddings AS vec
                JOIN chunk_embeddings AS embedding ON embedding.vector_rowid = vec.rowid
                JOIN indexed_chunks AS chunk ON chunk.id = embedding.chunk_id
                WHERE vec.embedding MATCH ? AND k = ?
                ORDER BY vec.distance
                """,
                (vector, limit),
            )
            return [_semantic_chunk(row) for row in rows]

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    vector_rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id TEXT NOT NULL UNIQUE,
                    content_hash TEXT NOT NULL,
                    embedding_model TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunk_embeddings "
                f"USING vec0(embedding float[{self._embedder.dimensions}])"
            )

    def _sync_chunk(self, connection: sqlite3.Connection, chunk: IndexedChunk) -> int:
        chunk_id = _chunk_id(chunk)
        row = connection.execute(
            """
            SELECT vector_rowid, content_hash, embedding_model
            FROM chunk_embeddings
            WHERE chunk_id = ?
            """,
            (chunk_id,),
        ).fetchone()
        if row is not None and row["content_hash"] == chunk.content_hash:
            if row["embedding_model"] == self._embedder.name:
                return 0
            connection.execute(
                "DELETE FROM vec_chunk_embeddings WHERE rowid = ?",
                (row["vector_rowid"],),
            )
            connection.execute("DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,))
        vector_rowid = connection.execute(
            """
            INSERT INTO chunk_embeddings(chunk_id, content_hash, embedding_model)
            VALUES (?, ?, ?)
            """,
            (chunk_id, chunk.content_hash, self._embedder.name),
        ).lastrowid
        connection.execute(
            "INSERT INTO vec_chunk_embeddings(rowid, embedding) VALUES (?, ?)",
            (vector_rowid, self._serialize(self._embedder.embed(chunk.content))),
        )
        return 1

    def _delete_removed_embeddings(
        self,
        connection: sqlite3.Connection,
        chunks: list[IndexedChunk],
    ) -> None:
        retained_ids = {_chunk_id(chunk) for chunk in chunks}
        rows = connection.execute("SELECT vector_rowid, chunk_id FROM chunk_embeddings")
        for row in rows:
            if str(row["chunk_id"]) in retained_ids:
                continue
            connection.execute(
                "DELETE FROM vec_chunk_embeddings WHERE rowid = ?",
                (row["vector_rowid"],),
            )
            connection.execute(
                "DELETE FROM chunk_embeddings WHERE chunk_id = ?",
                (row["chunk_id"],),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        module = self._module_loader()
        connection.enable_load_extension(True)
        load = cast(Callable[[sqlite3.Connection], None], getattr(module, "load"))
        load(connection)
        connection.enable_load_extension(False)
        return connection

    def _serialize(self, embedding: list[float]) -> Any:
        serialize = cast(Callable[[list[float]], Any], getattr(self._module_loader(), "serialize_float32"))
        return serialize(embedding)


def _semantic_chunk(row: sqlite3.Row) -> IndexedChunk:
    distance = max(0.0, float(row["distance"]))
    return IndexedChunk(
        file_path=str(row["file_path"]),
        chunk_type="vector",
        start_line=int(row["start_line"]),
        end_line=int(row["end_line"]),
        content=str(row["content"]),
        content_hash=str(row["content_hash"]),
        source_ref=str(row["source_ref"]),
        evidence_strength=0.6,
        source_authority=float(row["source_authority"]),
        freshness=float(row["freshness"]),
        semantic_score=1.0 / (1.0 + distance),
    )


def _chunk_id(chunk: IndexedChunk) -> str:
    return f"{chunk.file_path}:{chunk.start_line}:{chunk.content_hash}"


def _load_sqlite_vec_module() -> ModuleType:
    return importlib.import_module("sqlite_vec")
