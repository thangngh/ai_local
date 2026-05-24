from ai_local.knowledge.models import KnowledgeItem, SourceReference
from ai_local.knowledge.policy import decide_knowledge
from ai_local.memory.handoff import decide_knowledge_memory_write
from ai_local.memory.models import MemoryItem


def _knowledge(**overrides: object) -> KnowledgeItem:
    item = KnowledgeItem(
        claim="Project memory writes require explicit evidence.",
        level="K2_PROJECT",
        source_ref="docs/phase-05-entry-plan.md",
        confidence=0.86,
        rank=82,
        evidence_strength=0.80,
        conflict_score=0.10,
        source_refs=[
            SourceReference(
                ref="docs/phase-05-entry-plan.md",
                authority="project_doc",
                observed_at="2026-05-24",
            )
        ],
        evidence_refs=["docs/phase-05-entry-plan.md#source-requirements"],
        provenance="project_doc:docs/phase-05-entry-plan.md",
    )
    return item.model_copy(update=overrides)


def _memory(**overrides: object) -> MemoryItem:
    item = MemoryItem(
        claim="Project memory writes require explicit evidence.",
        scope="project",
        source="knowledge_gate",
        confidence=0.86,
        memory_level="M2_PROJECT_CONVENTION",
        evidence_strength=0.80,
        retrieval_score=0.80,
        status="candidate",
    )
    return item.model_copy(update=overrides)


def test_used_knowledge_can_seed_explicit_memory_evidence() -> None:
    decision = decide_knowledge_memory_write(decide_knowledge(_knowledge()), _memory())

    assert decision.decision == "accept_memory"
    assert decision.item.evidence_refs == ["docs/phase-05-entry-plan.md#source-requirements"]
    assert decision.item.source_hash == "docs/phase-05-entry-plan.md"


def test_unresolved_knowledge_does_not_silently_promote_to_memory() -> None:
    weak = decide_knowledge(_knowledge(rank=58, confidence=0.55, evidence_strength=0.45))
    conflict = decide_knowledge(_knowledge(conflict_score=0.75))
    rejected = decide_knowledge(_knowledge(level="K0_UNKNOWN", rank=20, evidence_strength=0.10))
    injected = decide_knowledge(_knowledge(noise_type="prompt_injection"))

    assert decide_knowledge_memory_write(weak, _memory()).decision == "verify"
    assert decide_knowledge_memory_write(conflict, _memory()).decision == "ask_user"
    assert decide_knowledge_memory_write(rejected, _memory()).decision == "reject_memory"
    assert decide_knowledge_memory_write(injected, _memory()).decision == "quarantine"


def test_confirmed_policy_knowledge_can_satisfy_confirmed_memory_layer() -> None:
    policy = decide_knowledge(
        _knowledge(
            level="K6_DECISION_POLICY",
            rank=96,
            confidence=0.95,
            evidence_strength=0.95,
        )
    )
    memory = _memory(memory_level="M3_CONFIRMED_DECISION", evidence_strength=0.90)

    decision = decide_knowledge_memory_write(policy, memory)

    assert decision.decision == "accept_memory"
    assert decision.item.confirmed
    assert decision.item.confirmed_by == "knowledge_gate"
