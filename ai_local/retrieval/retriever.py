from pathlib import Path

from ai_local.indexer.models import IndexedChunk, IndexedDocument
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.retrieval.fts import bilingual_aliases, normalize_query
from ai_local.retrieval.models import ContextPackage, RetrievalDecision, RetrievalHit, RetrievalQuery
from ai_local.retrieval.ripgrep import RipgrepMatch, rg_matches, rg_search
from ai_local.retrieval.vector import NullVectorProvider, VectorCandidateProvider


def retrieve_exact(query: str, root: Path) -> str:
    return rg_search(query, root)


def retrieve_local_exact(
    query: str,
    root: Path,
    *,
    max_hits: int = 5,
) -> ContextPackage:
    return retrieve_chunks(
        query,
        exact_match_chunks(rg_matches(query, root)),
        max_hits=max_hits,
    )


def exact_match_chunks(matches: list[RipgrepMatch]) -> list[IndexedChunk]:
    return [
        IndexedChunk(
            file_path=match.file_path,
            chunk_type="ripgrep_line",
            start_line=match.line_number,
            end_line=match.line_number,
            content=match.text,
            content_hash=f"rg:{match.file_path}:{match.line_number}:{match.text}",
            source_ref=f"{match.file_path}:{match.line_number}-{match.line_number}",
            evidence_strength=0.9,
            source_authority=0.8,
        )
        for match in matches
    ]


def build_query(query: str) -> RetrievalQuery:
    return RetrievalQuery(raw=query, normalized=normalize_query(query), aliases=bilingual_aliases(query))


def retrieve_chunks(
    query: str,
    chunks: list[IndexedChunk],
    *,
    active_flow: str | None = None,
    max_hits: int = 5,
) -> ContextPackage:
    retrieval_query = build_query(query)
    hits = [
        _chunk_hit(chunk, retrieval_query, active_flow=active_flow)
        for chunk in chunks
        if _candidate_matches(chunk, retrieval_query)
    ]
    ranked = sorted(hits, key=lambda hit: hit.score, reverse=True)
    decision, reason = decide_context(ranked)
    selected, rejected = pack_context(ranked, max_hits=max_hits)
    return ContextPackage(
        query=retrieval_query,
        hits=ranked,
        selected_hits=selected,
        rejected_hits=rejected,
        decision=decision,
        reason=reason,
    )


def retrieve_documents(
    query: str,
    documents: list[IndexedDocument],
    *,
    active_flow: str | None = None,
    max_hits: int = 5,
) -> ContextPackage:
    chunks = [chunk for document in documents for chunk in document.retrieval_chunks()]
    return retrieve_chunks(query, chunks, active_flow=active_flow, max_hits=max_hits)


def retrieve_index(
    query: str,
    store: KnowledgeIndexStore,
    *,
    active_flow: str | None = None,
    max_hits: int = 5,
    vector_chunks: list[IndexedChunk] | None = None,
    vector_provider: VectorCandidateProvider | None = None,
) -> ContextPackage:
    semantic_chunks = vector_chunks or (vector_provider or NullVectorProvider()).search(
        query,
        limit=max_hits * 2,
    )
    candidates = _dedupe_chunks(
        [
            *store.search_symbol_chunks(query, limit=max_hits * 2),
            *store.search_chunks(query, limit=max_hits * 4),
            *semantic_chunks,
        ]
    )
    return retrieve_chunks(
        query,
        candidates,
        active_flow=active_flow,
        max_hits=max_hits,
    )


def decide_context(hits: list[RetrievalHit]) -> tuple[RetrievalDecision, str]:
    if any("deep_policy_shadowing" in hit.flags for hit in hits):
        return "stop", "retrieval path shadows policy after deep hops"
    if any("deep_chain_interference" in hit.flags for hit in hits):
        return "ask_user", "deep retrieval chain needs evidence and decision review"
    if any("prompt_injection" in hit.flags for hit in hits):
        return "quarantine", "retrieved content has prompt injection flags"
    if any("source_conflict" in hit.flags for hit in hits):
        return "ask_user", "retrieved sources conflict"
    if any(hit.interference >= 0.60 or "stale" in hit.flags for hit in hits):
        return "verify", "retrieval needs verification"
    if hits:
        return "continue", "context package has ranked evidence"
    return "verify", "no indexed evidence matched"


def pack_context(
    hits: list[RetrievalHit],
    *,
    max_hits: int,
) -> tuple[list[RetrievalHit], list[RetrievalHit]]:
    usable = [hit for hit in hits if hit.usable]
    selected = usable[:max_hits]
    selected_ids = {hit.source_id for hit in selected}
    rejected = [hit for hit in hits if hit.source_id not in selected_ids]
    return selected, rejected


def _chunk_hit(
    chunk: IndexedChunk,
    query: RetrievalQuery,
    *,
    active_flow: str | None,
) -> RetrievalHit:
    flags = list(chunk.flags)
    flow_match = 1.0 if active_flow is not None and chunk.flow == active_flow else 0.0
    interference = 0.8 if active_flow is not None and chunk.flow not in {None, active_flow} else 0.0
    return RetrievalHit(
        source_id=f"{chunk.file_path}:{chunk.start_line}",
        source_ref=chunk.source_ref or f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}",
        content_hash=chunk.content_hash,
        text=chunk.content,
        source_type=chunk.chunk_type,
        lexical_score=_lexical_score(chunk.content, query.aliases),
        evidence_strength=chunk.evidence_strength,
        flow_match=flow_match,
        source_authority=chunk.source_authority,
        freshness=chunk.freshness,
        semantic_score=chunk.semantic_score,
        interference=interference,
        flags=flags,
    )


def _lexical_score(text: str, aliases: list[str]) -> float:
    normalized = normalize_query(text)
    terms = {
        term
        for alias in aliases
        for term in [alias, *alias.split()]
        if term
    }
    matches = sum(1 for term in terms if term in normalized)
    return min(1.0, matches / max(1, len(terms)))


def semantic_candidate(chunk: IndexedChunk, *, score: float) -> IndexedChunk:
    return IndexedChunk(
        file_path=chunk.file_path,
        chunk_type="vector",
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        content=chunk.content,
        content_hash=chunk.content_hash,
        source_ref=chunk.source_ref,
        symbol_refs=chunk.symbol_refs,
        flow=chunk.flow,
        evidence_strength=min(chunk.evidence_strength, 0.6),
        source_authority=chunk.source_authority,
        freshness=chunk.freshness,
        semantic_score=max(0.0, min(score, 1.0)),
        flags=chunk.flags,
    )


def _candidate_matches(chunk: IndexedChunk, query: RetrievalQuery) -> bool:
    return chunk.semantic_score > 0.0 or _lexical_score(chunk.content, query.aliases) > 0.0


def _dedupe_chunks(chunks: list[IndexedChunk]) -> list[IndexedChunk]:
    unique: dict[tuple[str, int, str], IndexedChunk] = {}
    for chunk in chunks:
        key = (chunk.file_path, chunk.start_line, chunk.content_hash)
        unique.setdefault(key, chunk)
    return list(unique.values())
