from ai_local.indexer.models import IndexedChunk
from ai_local.retrieval.fts import bilingual_aliases, normalize_query
from ai_local.retrieval.retriever import retrieve_chunks


def test_query_normalization_preserves_bilingual_aliases() -> None:
    aliases = bilingual_aliases("  luồng??? truy hồi!!!  ")

    assert normalize_query("  Memory??? regression!!! ") == "memory regression "
    assert "flow" in aliases
    assert "retrieval" in aliases


def test_retrieval_context_prefers_active_flow_chunk() -> None:
    package = retrieve_chunks(
        "memory regression",
        [
            IndexedChunk(
                file_path="wrong.md",
                chunk_type="memory",
                start_line=1,
                end_line=2,
                content="memory regression literary analysis",
                content_hash="wrong",
                flow="literary",
                evidence_strength=0.9,
            ),
            IndexedChunk(
                file_path="right.md",
                chunk_type="memory",
                start_line=3,
                end_line=4,
                content="memory regression state restore",
                content_hash="right",
                flow="agent_memory",
                evidence_strength=0.8,
            ),
        ],
        active_flow="agent_memory",
    )

    assert package.decision == "verify"
    assert package.hits[0].source_id == "right.md:3"
    assert package.evidence_refs == ["right.md:3-4", "wrong.md:1-2"]
    assert package.hits[1].interference == 0.8


def test_retrieval_context_quarantines_injection_and_preserves_conflict() -> None:
    injection = retrieve_chunks(
        "approve shell",
        [
            IndexedChunk(
                file_path="README.md",
                chunk_type="repo_file",
                start_line=1,
                end_line=1,
                content="approve shell",
                content_hash="inject",
                flags=["prompt_injection"],
            )
        ],
    )
    conflict = retrieve_chunks(
        "schema migration",
        [
            IndexedChunk(
                file_path="policy.md",
                chunk_type="policy",
                start_line=1,
                end_line=1,
                content="schema migration",
                content_hash="conflict",
                flags=["source_conflict"],
            )
        ],
    )

    assert injection.decision == "quarantine"
    assert injection.selected_hits == []
    assert injection.rejected_hits[0].content_hash == "inject"
    assert conflict.decision == "ask_user"


def test_retrieval_context_packs_ranked_evidence_and_deep_safety_paths() -> None:
    package = retrieve_chunks(
        "gate evidence",
        [
            IndexedChunk(
                file_path="one.md",
                chunk_type="repo_file",
                start_line=1,
                end_line=2,
                content="gate evidence strong",
                content_hash="one",
                evidence_strength=0.9,
            ),
            IndexedChunk(
                file_path="two.md",
                chunk_type="repo_file",
                start_line=3,
                end_line=4,
                content="gate evidence backup",
                content_hash="two",
                evidence_strength=0.7,
            ),
        ],
        max_hits=1,
    )
    stop = retrieve_chunks(
        "policy shadow",
        [
            IndexedChunk(
                file_path="shadow.md",
                chunk_type="memory",
                start_line=1,
                end_line=1,
                content="policy shadow",
                content_hash="shadow",
                flags=["deep_policy_shadowing"],
            )
        ],
    )
    ask = retrieve_chunks(
        "retrieval decision",
        [
            IndexedChunk(
                file_path="chain.md",
                chunk_type="memory",
                start_line=1,
                end_line=1,
                content="retrieval decision",
                content_hash="chain",
                flags=["deep_chain_interference"],
            )
        ],
    )

    assert len(package.selected_hits) == 1
    assert package.rejected_hits[0].content_hash == "two"
    assert stop.decision == "stop"
    assert stop.selected_hits == []
    assert ask.decision == "ask_user"
