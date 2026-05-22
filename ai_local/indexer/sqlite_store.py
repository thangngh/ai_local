from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ai_local.indexer.models import IndexedChunk, IndexedDocument, IndexManifestEntry


@dataclass(frozen=True)
class KnowledgeIndexStats:
    files: int
    chunks: int
    symbols: int


class KnowledgeIndexStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS indexed_files (
                    path TEXT PRIMARY KEY,
                    language TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    source_ref TEXT NOT NULL,
                    modified_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS indexed_chunks (
                    id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    chunk_type TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    symbol_refs_json TEXT NOT NULL,
                    flow TEXT,
                    evidence_strength REAL NOT NULL,
                    source_authority REAL NOT NULL,
                    freshness REAL NOT NULL,
                    flags_json TEXT NOT NULL,
                    FOREIGN KEY (file_path) REFERENCES indexed_files(path)
                );
                CREATE INDEX IF NOT EXISTS idx_indexed_chunks_file_path
                    ON indexed_chunks(file_path);
                CREATE TABLE IF NOT EXISTS indexed_symbols (
                    file_path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    source_ref TEXT NOT NULL,
                    PRIMARY KEY (file_path, kind, name, start_line),
                    FOREIGN KEY (file_path) REFERENCES indexed_files(path)
                );
                CREATE INDEX IF NOT EXISTS idx_indexed_symbols_name
                    ON indexed_symbols(name);
                CREATE VIRTUAL TABLE IF NOT EXISTS indexed_chunks_fts
                    USING fts5(chunk_id UNINDEXED, content);
                """
            )

    def upsert_documents(self, documents: Iterable[IndexedDocument]) -> None:
        with self._connect() as connection:
            for document in documents:
                self._replace_document(connection, document)

    def delete_paths(self, paths: Iterable[str]) -> None:
        with self._connect() as connection:
            for path in paths:
                self._delete_document(connection, path)

    def clear(self) -> None:
        self.delete_paths(self.manifest())

    def stats(self) -> KnowledgeIndexStats:
        with self._connect() as connection:
            files = connection.execute("SELECT COUNT(*) FROM indexed_files").fetchone()
            chunks = connection.execute("SELECT COUNT(*) FROM indexed_chunks").fetchone()
            symbols = connection.execute("SELECT COUNT(*) FROM indexed_symbols").fetchone()
            return KnowledgeIndexStats(
                files=int(files[0]) if files is not None else 0,
                chunks=int(chunks[0]) if chunks is not None else 0,
                symbols=int(symbols[0]) if symbols is not None else 0,
            )

    def manifest(self) -> dict[str, IndexManifestEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT path, content_hash, modified_ns FROM indexed_files ORDER BY path"
            )
            return {
                str(row["path"]): IndexManifestEntry(
                    path=str(row["path"]),
                    content_hash=str(row["content_hash"]),
                    modified_ns=int(row["modified_ns"]),
                )
                for row in rows
            }

    def search_chunks(self, query: str, *, limit: int = 20) -> list[IndexedChunk]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk.*
                FROM indexed_chunks_fts AS fts
                JOIN indexed_chunks AS chunk ON chunk.id = fts.chunk_id
                WHERE indexed_chunks_fts MATCH ?
                ORDER BY bm25(indexed_chunks_fts)
                LIMIT ?
                """,
                (_fts_query(query), limit),
            )
            return [_chunk_from_row(row) for row in rows]

    def search_symbol_chunks(self, query: str, *, limit: int = 20) -> list[IndexedChunk]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT chunk.*
                FROM indexed_symbols AS symbol
                JOIN indexed_chunks AS chunk
                    ON chunk.file_path = symbol.file_path
                    AND chunk.start_line <= symbol.end_line
                    AND chunk.end_line >= symbol.start_line
                WHERE lower(symbol.name) = lower(?)
                    OR lower(symbol.name) LIKE lower(?)
                ORDER BY
                    CASE WHEN lower(symbol.name) = lower(?) THEN 0 ELSE 1 END,
                    symbol.file_path,
                    symbol.start_line
                LIMIT ?
                """,
                (query, f"%{query}%", query, limit),
            )
            return [_symbol_chunk_from_row(row) for row in rows]

    def all_chunks(self) -> list[IndexedChunk]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM indexed_chunks ORDER BY file_path, start_line"
            )
            return [_chunk_from_row(row) for row in rows]

    def _replace_document(self, connection: sqlite3.Connection, document: IndexedDocument) -> None:
        self._delete_document(connection, document.file.path, keep_file=True)
        connection.execute(
            """
            INSERT INTO indexed_files(path, language, content_hash, size, source_ref, modified_ns)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                language = excluded.language,
                content_hash = excluded.content_hash,
                size = excluded.size,
                source_ref = excluded.source_ref,
                modified_ns = excluded.modified_ns
            """,
            (
                document.file.path,
                document.file.language,
                document.file.content_hash,
                document.file.size,
                document.file.source_ref,
                document.file.modified_ns,
            ),
        )
        for chunk in document.chunks:
            chunk_id = _chunk_id(chunk)
            connection.execute(
                """
                INSERT INTO indexed_chunks(
                    id, file_path, chunk_type, start_line, end_line, content, content_hash,
                    source_ref, symbol_refs_json, flow, evidence_strength, source_authority,
                    freshness, flags_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    chunk.file_path,
                    chunk.chunk_type,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.content,
                    chunk.content_hash,
                    chunk.source_ref or f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}",
                    json.dumps(chunk.symbol_refs),
                    chunk.flow,
                    chunk.evidence_strength,
                    chunk.source_authority,
                    chunk.freshness,
                    json.dumps(chunk.flags),
                ),
            )
            connection.execute(
                "INSERT INTO indexed_chunks_fts(chunk_id, content) VALUES (?, ?)",
                (chunk_id, chunk.content),
            )
        for symbol in document.symbols:
            connection.execute(
                """
                INSERT INTO indexed_symbols(
                    file_path, name, kind, start_line, end_line, source_ref
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    document.file.path,
                    symbol.name,
                    symbol.kind,
                    symbol.start_line,
                    symbol.end_line,
                    f"{document.file.path}:{symbol.start_line}-{symbol.end_line}",
                ),
            )

    def _delete_document(
        self,
        connection: sqlite3.Connection,
        file_path: str,
        *,
        keep_file: bool = False,
    ) -> None:
        existing_ids = [
            str(row["id"])
            for row in connection.execute(
                "SELECT id FROM indexed_chunks WHERE file_path = ?",
                (file_path,),
            )
        ]
        for chunk_id in existing_ids:
            connection.execute("DELETE FROM indexed_chunks_fts WHERE chunk_id = ?", (chunk_id,))
        connection.execute("DELETE FROM indexed_symbols WHERE file_path = ?", (file_path,))
        connection.execute("DELETE FROM indexed_chunks WHERE file_path = ?", (file_path,))
        if not keep_file:
            connection.execute("DELETE FROM indexed_files WHERE path = ?", (file_path,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _chunk_id(chunk: IndexedChunk) -> str:
    return f"{chunk.file_path}:{chunk.start_line}:{chunk.content_hash}"


def _chunk_from_row(row: sqlite3.Row) -> IndexedChunk:
    return IndexedChunk(
        file_path=str(row["file_path"]),
        chunk_type=str(row["chunk_type"]),
        start_line=int(row["start_line"]),
        end_line=int(row["end_line"]),
        content=str(row["content"]),
        content_hash=str(row["content_hash"]),
        source_ref=str(row["source_ref"]),
        symbol_refs=[str(item) for item in json.loads(str(row["symbol_refs_json"]))],
        flow=str(row["flow"]) if row["flow"] is not None else None,
        evidence_strength=float(row["evidence_strength"]),
        source_authority=float(row["source_authority"]),
        freshness=float(row["freshness"]),
        flags=[str(item) for item in json.loads(str(row["flags_json"]))],
    )


def _symbol_chunk_from_row(row: sqlite3.Row) -> IndexedChunk:
    chunk = _chunk_from_row(row)
    return IndexedChunk(
        file_path=chunk.file_path,
        chunk_type="symbol",
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        content=chunk.content,
        content_hash=chunk.content_hash,
        source_ref=chunk.source_ref,
        symbol_refs=chunk.symbol_refs,
        flow=chunk.flow,
        evidence_strength=max(0.8, chunk.evidence_strength),
        source_authority=max(0.8, chunk.source_authority),
        freshness=chunk.freshness,
        semantic_score=chunk.semantic_score,
        flags=chunk.flags,
    )


def _fts_query(query: str) -> str:
    terms = [term for term in query.replace('"', " ").split() if term]
    return " AND ".join(f'"{term}"' for term in terms) or '""'
