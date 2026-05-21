from ai_local.knowledge.conflicts import resolve_conflict
from ai_local.knowledge.harness import accept_item
from ai_local.knowledge.models import ConflictCandidate, EvidenceSignal, KnowledgeItem
from ai_local.knowledge.policy import decide_knowledge
from ai_local.knowledge.ranker import rank_evidence


def _item(**overrides: object) -> KnowledgeItem:
    item = KnowledgeItem(
        claim="Project requires patch evidence before promotion.",
        level="K2_PROJECT",
        source_ref="docs/requirements.md",
        confidence=0.86,
        rank=82,
        evidence_strength=0.80,
        conflict_score=0.10,
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


def test_multi_instance_conflict_resolution_preserves_no_winner_paths() -> None:
    candidates = [_candidate("memory"), _candidate("retrieval")]

    assert resolve_conflict("multi_instance_tie", candidates).decision == "ask_user"
    assert resolve_conflict("missing_test_evidence", candidates).decision == "defer_until_evidence"
    assert resolve_conflict("no_safe_path", candidates).decision == "stop"
