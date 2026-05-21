from pathlib import Path

from ai_local.indexer.models import IndexedChunk, IndexedDocument
from ai_local.retrieval.fts import bilingual_aliases, normalize_query
from ai_local.retrieval.models import ContextPackage, RetrievalDecision, RetrievalHit, RetrievalQuery
from ai_local.retrieval.ripgrep import rg_search


def retrieve_exact(query: str, root: Path) -> str:
    return rg_search(query, root)


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
        if _lexical_score(chunk.content, retrieval_query.aliases) > 0.0
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
        interference=interference,
        flags=flags,
    )


def _lexical_score(text: str, aliases: list[str]) -> float:
    normalized = normalize_query(text)
    matches = sum(1 for alias in aliases if alias and alias in normalized)
    return min(1.0, matches / max(1, len(aliases)))
