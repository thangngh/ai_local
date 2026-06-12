from dataclasses import dataclass
from pathlib import Path

from ai_local.indexer.models import IndexBatchResult
from ai_local.indexer.scanner import index_changed_paths, scan_files
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.retrieval.models import ContextPackage
from ai_local.retrieval.retriever import retrieve_index
from ai_local.retrieval.vector import VectorCandidateProvider


@dataclass(frozen=True)
class ProjectIndexRetrieval:
    batch: IndexBatchResult
    package: ContextPackage


@dataclass(frozen=True)
class ProjectRetriever:
    root: Path
    store: KnowledgeIndexStore
    chunk_lines: int = 40
    max_hits: int = 5
    vector_provider: VectorCandidateProvider | None = None

    def retrieve(self, query: str) -> ContextPackage:
        return refresh_and_retrieve_project(
            query,
            self.root,
            self.store,
            chunk_lines=self.chunk_lines,
            max_hits=self.max_hits,
            vector_provider=self.vector_provider,
        ).package


def refresh_project_index(
    root: Path,
    store: KnowledgeIndexStore,
    *,
    chunk_lines: int = 40,
    clear_store: bool = False,
) -> IndexBatchResult:
    store.initialize()
    if clear_store:
        store.clear()
    paths = scan_files(root)
    scanned_refs = {_project_ref(path, root) for path in paths}
    previous_manifest = store.manifest()
    deleted_paths = sorted(set(previous_manifest) - scanned_refs)
    batch = index_changed_paths(
        paths,
        root=root,
        manifest=previous_manifest,
        chunk_lines=chunk_lines,
    )
    store.delete_paths(deleted_paths)
    store.upsert_documents(batch.documents)
    return IndexBatchResult(
        documents=batch.documents,
        manifest={path: entry for path, entry in batch.manifest.items() if path not in deleted_paths},
        skipped_paths=batch.skipped_paths,
        unchanged_paths=batch.unchanged_paths,
        deleted_paths=deleted_paths,
    )


def rebuild_project_index(
    root: Path,
    store: KnowledgeIndexStore,
    *,
    chunk_lines: int = 40,
) -> IndexBatchResult:
    store.initialize()
    store.clear()
    return refresh_project_index(root, store, chunk_lines=chunk_lines)


def refresh_and_retrieve_project(
    query: str,
    root: Path,
    store: KnowledgeIndexStore,
    *,
    chunk_lines: int = 40,
    max_hits: int = 5,
    vector_provider: VectorCandidateProvider | None = None,
    clear_store: bool = False,
) -> ProjectIndexRetrieval:
    batch = refresh_project_index(root, store, chunk_lines=chunk_lines, clear_store=clear_store)
    package = retrieve_index(
        query,
        store,
        max_hits=max_hits,
        vector_provider=vector_provider,
    )
    return ProjectIndexRetrieval(batch=batch, package=package)


def _project_ref(path: Path, root: Path) -> str:
    return str(path.relative_to(root))
