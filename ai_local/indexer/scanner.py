from hashlib import sha256
from pathlib import Path

from ai_local.indexer.models import (
    IndexBatchResult,
    IndexedChunk,
    IndexedDocument,
    IndexedFile,
    IndexManifestEntry,
)
from ai_local.indexer.symbols import Symbol, SymbolExtractor, extract_symbols

_TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".sql",
    ".js",
    ".ts",
    ".tsx",
}


def scan_files(root: Path, *, include_suffixes: set[str] | None = None) -> list[Path]:
    suffixes = include_suffixes or _TEXT_SUFFIXES
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in suffixes and not _ignored_path(path)
    )


def index_paths(
    paths: list[Path],
    *,
    root: Path | None = None,
    chunk_lines: int = 40,
    symbol_extractors: dict[str, SymbolExtractor] | None = None,
) -> list[IndexedDocument]:
    return [
        index_file(
            path,
            root=root,
            chunk_lines=chunk_lines,
            symbol_extractors=symbol_extractors,
        )
        for path in paths
    ]


def index_changed_paths(
    paths: list[Path],
    *,
    root: Path | None = None,
    manifest: dict[str, IndexManifestEntry] | None = None,
    chunk_lines: int = 40,
    symbol_extractors: dict[str, SymbolExtractor] | None = None,
) -> IndexBatchResult:
    previous = manifest or {}
    documents: list[IndexedDocument] = []
    next_manifest = dict(previous)
    skipped_paths: list[str] = []
    unchanged_paths: list[str] = []
    for path in paths:
        try:
            document = index_file(
                path,
                root=root,
                chunk_lines=chunk_lines,
                symbol_extractors=symbol_extractors,
            )
        except UnicodeDecodeError:
            skipped_paths.append(_path_ref(path, root))
            continue
        entry = IndexManifestEntry(
            path=document.file.path,
            content_hash=document.file.content_hash,
            modified_ns=document.file.modified_ns,
        )
        if _unchanged(previous.get(document.file.path), entry):
            unchanged_paths.append(document.file.path)
            next_manifest[document.file.path] = entry
            continue
        documents.append(document)
        next_manifest[document.file.path] = entry
    return IndexBatchResult(documents, next_manifest, skipped_paths, unchanged_paths)


def index_file(
    path: Path,
    *,
    root: Path | None = None,
    chunk_lines: int = 40,
    symbol_extractors: dict[str, SymbolExtractor] | None = None,
) -> IndexedDocument:
    content = path.read_text(encoding="utf-8")
    relative_path = str(path.relative_to(root)) if root is not None else str(path)
    stat = path.stat()
    file_hash = _hash_text(content)
    language = _language_for(path)
    indexed_file = IndexedFile(
        path=relative_path,
        language=language,
        content_hash=file_hash,
        size=len(content.encode("utf-8")),
        source_ref=f"file:{relative_path}",
        modified_ns=stat.st_mtime_ns,
    )
    symbols = extract_symbols(content, language, extractors=symbol_extractors)
    chunks = chunk_text(relative_path, content, chunk_lines=chunk_lines, symbols=symbols)
    return IndexedDocument(file=indexed_file, chunks=chunks, symbols=symbols)


def chunk_text(
    file_path: str,
    content: str,
    *,
    chunk_lines: int = 40,
    symbols: list[Symbol] | None = None,
) -> list[IndexedChunk]:
    lines = content.splitlines()
    if not lines:
        return []
    chunks: list[IndexedChunk] = []
    for offset in range(0, len(lines), chunk_lines):
        chunk_lines_text = lines[offset : offset + chunk_lines]
        chunk_content = "\n".join(chunk_lines_text)
        chunks.append(
            IndexedChunk(
                file_path=file_path,
                chunk_type="text",
                start_line=offset + 1,
                end_line=offset + len(chunk_lines_text),
                content=chunk_content,
                content_hash=_hash_text(chunk_content),
                source_ref=f"{file_path}:{offset + 1}-{offset + len(chunk_lines_text)}",
                symbol_refs=_symbol_refs(
                    symbols or [],
                    start_line=offset + 1,
                    end_line=offset + len(chunk_lines_text),
                ),
            )
        )
    return chunks


def _hash_text(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _language_for(path: Path) -> str:
    return {
        "py": "python",
        "md": "markdown",
        "js": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
    }.get(path.suffix.lstrip("."), "text")


def _symbol_refs(symbols: list[Symbol], *, start_line: int, end_line: int) -> list[str]:
    return [
        f"{symbol.kind}:{symbol.name}"
        for symbol in symbols
        if symbol.start_line <= end_line and symbol.end_line >= start_line
    ]


def _unchanged(previous: IndexManifestEntry | None, current: IndexManifestEntry) -> bool:
    return (
        previous is not None
        and previous.content_hash == current.content_hash
        and previous.modified_ns == current.modified_ns
    )


def _ignored_path(path: Path) -> bool:
    return any(part in {".git", ".venv", "__pycache__", "node_modules"} for part in path.parts)


def _path_ref(path: Path, root: Path | None) -> str:
    return str(path.relative_to(root)) if root is not None else str(path)
