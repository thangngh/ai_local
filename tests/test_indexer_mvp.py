from pathlib import Path

from ai_local.indexer.models import IndexedChunk
from ai_local.indexer.scanner import (
    chunk_text,
    index_changed_paths,
    index_file,
    index_paths,
    scan_files,
)
from ai_local.indexer.project import rebuild_project_index, refresh_and_retrieve_project
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.retrieval.retriever import retrieve_documents
from ai_local.retrieval.retriever import retrieve_index, semantic_candidate
from ai_local.indexer.symbols import Symbol, extract_python_symbols
from ai_local.retrieval.vector import NullVectorProvider


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
    assert document.file.modified_ns > 0
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


def test_index_file_accepts_optional_symbol_extractor_for_typescript(tmp_path: Path) -> None:
    source = tmp_path / "service.ts"
    source.write_text("export function buildContext() { return 1; }\n", encoding="utf-8")

    class StaticTypeScriptExtractor:
        def extract(self, content: str) -> list[Symbol]:
            assert "buildContext" in content
            return [Symbol(name="buildContext", kind="function", start_line=1, end_line=1)]

    document = index_file(
        source,
        root=tmp_path,
        symbol_extractors={"typescript": StaticTypeScriptExtractor()},
    )

    assert document.file.language == "typescript"
    assert document.chunks[0].symbol_refs == ["function:buildContext"]


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


def test_changed_index_skips_binary_and_unchanged_files(tmp_path: Path) -> None:
    source = tmp_path / "service.py"
    source.write_text("def load():\n    return 'memory'\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(bytes([255, 254, 0]))

    scanned = scan_files(tmp_path)
    first = index_changed_paths(scanned + [tmp_path / "blob.bin"], root=tmp_path)
    second = index_changed_paths(scanned, root=tmp_path, manifest=first.manifest)
    source.write_text("def load():\n    return 'knowledge'\n", encoding="utf-8")
    third = index_changed_paths(scanned, root=tmp_path, manifest=second.manifest)

    assert [path.name for path in scanned] == ["service.py"]
    assert [document.file.path for document in first.documents] == ["service.py"]
    assert first.skipped_paths == ["blob.bin"]
    assert second.documents == []
    assert second.unchanged_paths == ["service.py"]
    assert [document.file.path for document in third.documents] == ["service.py"]


def test_scan_files_ignores_generated_and_runtime_dirs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "cart.store.ts").write_text("export const cart = true\n", encoding="utf-8")
    for generated in [".next", "node_modules", ".ai-local", "dist", "coverage"]:
        folder = tmp_path / generated
        folder.mkdir()
        (folder / "ignored.ts").write_text("ignore me\n", encoding="utf-8")

    scanned = scan_files(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in scanned] == ["src/cart.store.ts"]


def test_sqlite_knowledge_index_persists_manifest_and_fts_chunks(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "policy.md"
    source.write_text("memory policy requires evidence\n", encoding="utf-8")
    document = index_file(source, root=tmp_path, chunk_lines=2)
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")
    store.initialize()

    store.upsert_documents([document])
    package = retrieve_index("memory evidence", store)
    source.write_text("queue retry requires audit\n", encoding="utf-8")
    changed = index_file(source, root=tmp_path, chunk_lines=2)
    store.upsert_documents([changed])

    assert package.decision == "continue"
    assert package.evidence_refs == ["docs\\policy.md:1-1"]
    assert store.manifest()["docs\\policy.md"].content_hash == changed.file.content_hash
    assert store.search_chunks("memory evidence") == []
    assert store.search_chunks("queue audit")[0].source_ref == "docs\\policy.md:1-1"


def test_sqlite_knowledge_index_promotes_symbol_chunks_for_code_lookup(tmp_path: Path) -> None:
    source = tmp_path / "agent.py"
    source.write_text(
        "def build_context_package():\n"
        "    return 'queue retry evidence'\n",
        encoding="utf-8",
    )
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")
    store.initialize()
    store.upsert_documents([index_file(source, root=tmp_path, chunk_lines=4)])

    symbol_chunks = store.search_symbol_chunks("build_context_package")
    package = retrieve_index("build_context_package", store)
    source.write_text(
        "def build_symbol_context():\n"
        "    return 'queue retry evidence'\n",
        encoding="utf-8",
    )
    store.upsert_documents([index_file(source, root=tmp_path, chunk_lines=4)])

    assert symbol_chunks[0].chunk_type == "symbol"
    assert symbol_chunks[0].source_ref == "agent.py:1-2"
    assert symbol_chunks[0].symbol_refs == ["function:build_context_package"]
    assert package.decision == "continue"
    assert package.selected_hits[0].source_type == "symbol"
    assert store.search_symbol_chunks("build_context_package") == []
    assert store.search_symbol_chunks("build_symbol_context")[0].symbol_refs == [
        "function:build_symbol_context"
    ]


def test_sqlite_retrieval_merges_optional_vector_candidates(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("queue retry policy\n", encoding="utf-8")
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")
    store.initialize()
    store.upsert_documents([index_file(source, root=tmp_path)])
    vector_only = semantic_candidate(
        chunk_text("semantic.md", "worker recovery note", chunk_lines=4)[0],
        score=0.9,
    )

    package = retrieve_index("queue retry policy", store, vector_chunks=[vector_only])

    assert package.decision == "continue"
    assert [hit.source_type for hit in package.selected_hits] == ["text", "vector"]


def test_project_refresh_persists_changed_files_before_retrieval(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "retrieval.md"
    source.parent.mkdir()
    source.write_text("queue retry evidence\n", encoding="utf-8")
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")

    first = refresh_and_retrieve_project("queue retry", tmp_path, store, chunk_lines=4)
    second = refresh_and_retrieve_project("queue retry", tmp_path, store, chunk_lines=4)
    source.write_text("memory lookup evidence\n", encoding="utf-8")
    third = refresh_and_retrieve_project("memory lookup", tmp_path, store, chunk_lines=4)

    assert [document.file.path for document in first.batch.documents] == [
        "docs\\retrieval.md"
    ]
    assert first.package.evidence_refs == ["docs\\retrieval.md:1-1"]
    assert second.batch.documents == []
    assert second.batch.unchanged_paths == ["docs\\retrieval.md"]
    assert [document.file.path for document in third.batch.documents] == [
        "docs\\retrieval.md"
    ]
    assert third.package.evidence_refs == ["docs\\retrieval.md:1-1"]


def test_project_refresh_deletes_removed_project_files(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "stale.md"
    source.parent.mkdir()
    source.write_text("stale retrieval evidence\n", encoding="utf-8")
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")

    first = refresh_and_retrieve_project("stale retrieval", tmp_path, store)
    source.unlink()
    second = refresh_and_retrieve_project("stale retrieval", tmp_path, store)

    assert first.package.decision == "continue"
    assert second.batch.deleted_paths == ["docs\\stale.md"]
    assert second.package.decision == "verify"
    assert store.manifest() == {}
    assert store.stats().files == 0


def test_project_refresh_accepts_vector_provider_boundary(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("queue retry policy\n", encoding="utf-8")
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")
    vector_only = semantic_candidate(
        chunk_text("semantic.md", "worker recovery note", chunk_lines=4)[0],
        score=0.9,
    )

    class StaticVectorProvider:
        def search(self, query: str, *, limit: int) -> list[IndexedChunk]:
            assert query == "queue retry policy"
            assert limit == 10
            return [vector_only]

    with_vectors = refresh_and_retrieve_project(
        "queue retry policy",
        tmp_path,
        store,
        vector_provider=StaticVectorProvider(),
    )
    fallback = retrieve_index("queue retry policy", store, vector_provider=NullVectorProvider())

    assert [hit.source_type for hit in with_vectors.package.selected_hits] == ["text", "vector"]
    assert [hit.source_type for hit in fallback.selected_hits] == ["text"]


def test_project_rebuild_replaces_existing_index_rows(tmp_path: Path) -> None:
    source = tmp_path / "docs.md"
    source.write_text("old evidence\n", encoding="utf-8")
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")
    refresh_and_retrieve_project("old evidence", tmp_path, store)
    source.write_text("new evidence\n", encoding="utf-8")

    rebuilt = rebuild_project_index(tmp_path, store)

    assert [document.file.path for document in rebuilt.documents] == ["docs.md"]
    assert store.search_chunks("old evidence") == []
    assert store.search_chunks("new evidence")[0].source_ref == "docs.md:1-1"
