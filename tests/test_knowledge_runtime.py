from ai_local.knowledge.conflicts import resolve_conflict
from ai_local.knowledge.harness import accept_item
from ai_local.knowledge.models import ConflictCandidate, EvidenceSignal, KnowledgeItem, SourceReference
from ai_local.knowledge.policy import decide_knowledge
from ai_local.knowledge.ranker import rank_evidence
from ai_local.knowledge.store import InMemoryKnowledgeStore


def _item(**overrides: object) -> KnowledgeItem:
    item = KnowledgeItem(
        claim="Project requires patch evidence before promotion.",
        level="K2_PROJECT",
        source_ref="docs/requirements.md",
        confidence=0.86,
        rank=82,
        evidence_strength=0.80,
        conflict_score=0.10,
        source_refs=[
            SourceReference(
                ref="docs/requirements.md",
                authority="project_doc",
                snippet="Evidence and tests gate confident claims.",
                observed_at="2026-05-24",
            )
        ],
        evidence_refs=["tests/harness/test_knowledge_gate.py::test_knowledge_promotion_passes_all_levels"],
        provenance="project_doc:docs/requirements.md",
    )
    return item.model_copy(update=overrides)


def _candidate(candidate_id: str) -> ConflictCandidate:
    return ConflictCandidate(
        id=candidate_id,
        evidence_rank=76,
        risk=0.35,
        authority="K2_PROJECT",
    )


def test_knowledge_policy_uses_project_evidence_and_rejects_unknown() -> None:
    accepted = _item()
    unknown = _item(level="K0_UNKNOWN", rank=20, confidence=0.20, evidence_strength=0.10)

    assert decide_knowledge(accepted).decision == "use"
    assert accept_item(accepted)
    assert decide_knowledge(unknown).decision == "reject"


def test_knowledge_policy_verifies_conflicts_and_quarantines_injection() -> None:
    current = _item(level="K3_CURRENT", evidence_strength=0.45, rank=58, confidence=0.55)
    conflict = _item(conflict_score=0.75)
    injected = _item(noise_type="prompt_injection")
    laundered = _item(level="K6_DECISION_POLICY", noise_type="deep_policy_laundering")

    assert decide_knowledge(current).decision == "verify_more"
    assert decide_knowledge(conflict).decision == "ask_user"
    assert decide_knowledge(injected).decision == "quarantine"
    assert decide_knowledge(laundered).decision == "reject"


def test_knowledge_policy_requires_refs_for_high_rank_and_current_claims() -> None:
    no_evidence_refs = _item(evidence_refs=[])
    stale_current = _item(level="K3_CURRENT", source_refs=[])
    fresh_current = _item(
        level="K3_CURRENT",
        rank=78,
        confidence=0.78,
        evidence_strength=0.72,
        source_refs=[
            SourceReference(
                ref="https://example.test/api",
                authority="primary_external",
                observed_at="2026-05-24",
            )
        ],
    )

    assert decide_knowledge(no_evidence_refs).decision == "verify_more"
    assert decide_knowledge(stale_current).decision == "verify_more"
    assert decide_knowledge(fresh_current).decision == "use"


def test_evidence_rank_bands_and_hard_reject_noise() -> None:
    canonical = EvidenceSignal(
        source_authority=30,
        evidence_strength=25,
        freshness=15,
        project_relevance=15,
        confirmation_weight=15,
    )
    weak = EvidenceSignal(
        source_authority=20,
        evidence_strength=18,
        freshness=8,
        project_relevance=12,
        confirmation_weight=0,
        conflict_penalty=5,
        staleness_penalty=10,
        noise_type="stale_docs",
    )
    injected = canonical.model_copy(update={"noise_type": "prompt_injection"})

    assert (rank_evidence(canonical).rank, rank_evidence(canonical).band) == (100, "canonical")
    assert rank_evidence(weak).band == "weak"
    assert rank_evidence(injected).band == "reject"


def test_evidence_rank_caps_unknown_source_authority() -> None:
    inflated_unknown = EvidenceSignal(
        source_authority=30,
        evidence_strength=25,
        freshness=15,
        project_relevance=15,
        confirmation_weight=15,
        noise_type="unknown_source",
    )

    rank = rank_evidence(inflated_unknown)

    assert rank.rank == 78
    assert rank.band == "strong"
    assert rank.reason == "unknown source authority capped before rank formula"


def test_multi_instance_conflict_resolution_preserves_no_winner_paths() -> None:
    candidates = [_candidate("memory"), _candidate("retrieval")]

    assert resolve_conflict("multi_instance_tie", candidates).decision == "ask_user"
    assert resolve_conflict("missing_test_evidence", candidates).decision == "defer_until_evidence"
    assert resolve_conflict("no_safe_path", candidates).decision == "stop"


def test_multi_instance_conflict_selects_clear_low_risk_winner() -> None:
    candidates = [
        ConflictCandidate(id="project_doc", evidence_rank=90, risk=0.25, authority="K2_PROJECT"),
        ConflictCandidate(id="stale_memory", evidence_rank=72, risk=0.30, authority="K2_PROJECT"),
    ]

    resolution = resolve_conflict("multi_instance_tie", candidates)

    assert resolution.decision == "use_candidate"
    assert resolution.selected_candidate_id == "project_doc"


def test_in_memory_knowledge_store_finds_claims_and_conflicts() -> None:
    store = InMemoryKnowledgeStore()
    stable = _item()
    conflicting = _item(source_ref="docs/old-requirements.md", conflict_score=0.80)
    store.add(stable)
    store.add(conflicting)

    assert len(store.find_by_claim(" project requires patch evidence before promotion. ")) == 2
    assert store.find_conflicts(stable) == (conflicting,)
