from pathlib import Path

from ai_local.indexer.scanner import chunk_text, index_file, index_paths, scan_files
from ai_local.retrieval.retriever import retrieve_documents
from ai_local.indexer.symbols import extract_python_symbols


def test_index_file_builds_metadata_chunks_and_symbols(tmp_path: Path) -> None:
    source = tmp_path / "service.py"
    source.write_text(
        "class Service:\n"
        "    pass\n\n"
        "def build_service():\n"
        "    return Service()\n",
        encoding="utf-8",
    )

    document = index_file(source, root=tmp_path, chunk_lines=2)

    assert document.file.path == "service.py"
    assert document.file.language == "python"
    assert document.file.source_ref == "file:service.py"
    assert len(document.file.content_hash) == 64
    assert [chunk.start_line for chunk in document.chunks] == [1, 3, 5]
    assert document.chunks[0].symbol_refs == ["class:Service"]
    assert document.chunks[1].symbol_refs == ["function:build_service"]
    assert [symbol.name for symbol in document.symbols] == ["Service", "build_service"]


def test_chunk_text_keeps_line_ranges_for_retrieval() -> None:
    chunks = chunk_text("docs.md", "one\ntwo\nthree", chunk_lines=2)

    assert [(chunk.start_line, chunk.end_line) for chunk in chunks] == [(1, 2), (3, 3)]
    assert chunks[0].file_path == "docs.md"
    assert chunks[0].source_ref == "docs.md:1-2"


def test_extract_python_symbols_reports_function_and_class_ranges() -> None:
    symbols = extract_python_symbols("async def load():\n    return 1\n")

    assert symbols[0].name == "load"
    assert symbols[0].kind == "function"


def test_index_batch_feeds_retrieval_documents(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "memory.md").write_text("memory schema evidence\n", encoding="utf-8")
    (docs / "queue.md").write_text("queue retry policy\n", encoding="utf-8")

    indexed = index_paths(scan_files(docs), root=tmp_path, chunk_lines=2)
    package = retrieve_documents("memory schema", indexed)

    assert [document.file.path for document in indexed] == ["docs\\memory.md", "docs\\queue.md"]
    assert package.decision == "continue"
    assert package.evidence_refs == ["docs\\memory.md:1-1"]
