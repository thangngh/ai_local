from pathlib import Path

import pytest

from ai_local.indexer.scanner import index_file
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.retrieval.sqlite_vec import SqliteVecProvider
from ai_local.retrieval.vector import HashingTextEmbedder


def test_sqlite_vec_provider_reports_missing_optional_binding(tmp_path: Path) -> None:
    provider = SqliteVecProvider(tmp_path / "knowledge.db", HashingTextEmbedder())

    if SqliteVecProvider.is_available():
        pytest.skip("sqlite-vec optional dependency is installed")

    with pytest.raises(ModuleNotFoundError):
        provider.initialize()


@pytest.mark.skipif(not SqliteVecProvider.is_available(), reason="sqlite-vec extra is absent")
def test_sqlite_vec_provider_syncs_and_searches_indexed_chunks(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("queue retry evidence\n", encoding="utf-8")
    store = KnowledgeIndexStore(tmp_path / "knowledge.db")
    store.initialize()
    store.upsert_documents([index_file(source, root=tmp_path)])
    provider = SqliteVecProvider(store.db_path, HashingTextEmbedder(dimensions=8))

    synced = provider.sync(store)
    matches = provider.search("queue retry", limit=2)

    assert synced == 1
    assert matches[0].source_ref == "notes.md:1-1"
    assert matches[0].chunk_type == "vector"
