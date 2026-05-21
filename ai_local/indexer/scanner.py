from hashlib import sha256
from pathlib import Path

from ai_local.indexer.models import IndexedChunk, IndexedDocument, IndexedFile
from ai_local.indexer.symbols import Symbol, extract_python_symbols


def scan_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def index_paths(
    paths: list[Path],
    *,
    root: Path | None = None,
    chunk_lines: int = 40,
) -> list[IndexedDocument]:
    return [index_file(path, root=root, chunk_lines=chunk_lines) for path in paths]


def index_file(path: Path, *, root: Path | None = None, chunk_lines: int = 40) -> IndexedDocument:
    content = path.read_text(encoding="utf-8")
    relative_path = str(path.relative_to(root)) if root is not None else str(path)
    file_hash = _hash_text(content)
    language = _language_for(path)
    indexed_file = IndexedFile(
        path=relative_path,
        language=language,
        content_hash=file_hash,
        size=len(content.encode("utf-8")),
        source_ref=f"file:{relative_path}",
    )
    symbols = extract_python_symbols(content) if language == "python" else []
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
    return {"py": "python", "md": "markdown"}.get(path.suffix.lstrip("."), "text")


def _symbol_refs(symbols: list[Symbol], *, start_line: int, end_line: int) -> list[str]:
    return [
        f"{symbol.kind}:{symbol.name}"
        for symbol in symbols
        if symbol.start_line <= end_line and symbol.end_line >= start_line
    ]
