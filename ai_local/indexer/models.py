from dataclasses import dataclass, field

from ai_local.indexer.symbols import Symbol


@dataclass(frozen=True)
class IndexedFile:
    path: str
    language: str
    content_hash: str
    size: int
    source_ref: str
    modified_ns: int = 0


@dataclass(frozen=True)
class IndexedChunk:
    file_path: str
    chunk_type: str
    start_line: int
    end_line: int
    content: str
    content_hash: str
    source_ref: str | None = None
    symbol_refs: list[str] = field(default_factory=list)
    flow: str | None = None
    evidence_strength: float = 0.5
    source_authority: float = 0.5
    freshness: float = 1.0
    semantic_score: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IndexedDocument:
    file: IndexedFile
    chunks: list[IndexedChunk]
    symbols: list[Symbol]

    def retrieval_chunks(self) -> list[IndexedChunk]:
        return self.chunks


@dataclass(frozen=True)
class IndexManifestEntry:
    path: str
    content_hash: str
    modified_ns: int


@dataclass(frozen=True)
class IndexBatchResult:
    documents: list[IndexedDocument]
    manifest: dict[str, IndexManifestEntry]
    skipped_paths: list[str]
    unchanged_paths: list[str]
    deleted_paths: list[str] = field(default_factory=list)
