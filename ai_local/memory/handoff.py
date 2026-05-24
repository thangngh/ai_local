from ai_local.knowledge.models import KnowledgeGateDecision
from ai_local.memory.models import MemoryDecision, MemoryItem
from ai_local.memory.policy import decide_write


def decide_knowledge_memory_write(
    knowledge: KnowledgeGateDecision,
    memory: MemoryItem,
) -> MemoryDecision:
    if knowledge.decision == "quarantine":
        quarantined = memory.model_copy(update={"status": "quarantined"})
        return MemoryDecision(
            item=quarantined,
            decision="quarantine",
            reason="knowledge claim is quarantined before memory write",
        )
    if knowledge.decision == "reject":
        return MemoryDecision(
            item=memory,
            decision="reject_memory",
            reason="rejected knowledge cannot be promoted to memory",
        )
    if knowledge.decision == "ask_user":
        return MemoryDecision(
            item=memory,
            decision="ask_user",
            reason="knowledge conflict requires user confirmation before memory write",
        )
    if knowledge.decision == "verify_more":
        return MemoryDecision(
            item=memory,
            decision="verify",
            reason="knowledge needs stronger evidence before memory write",
        )

    evidenced_memory = _attach_knowledge_evidence(knowledge, memory)
    return decide_write(evidenced_memory)


def _attach_knowledge_evidence(
    knowledge: KnowledgeGateDecision,
    memory: MemoryItem,
) -> MemoryItem:
    item = knowledge.item
    evidence_refs = memory.evidence_refs or list(item.evidence_refs)
    source_hash = memory.source_hash or _source_hash_seed(item.all_source_refs)
    confirmed_by = memory.confirmed_by
    if item.level in {"K5_GROUND_TRUTH", "K6_DECISION_POLICY"} and item.confidence >= 0.90:
        confirmed_by = confirmed_by or "knowledge_gate"
    return memory.model_copy(
        update={
            "evidence_refs": evidence_refs,
            "source_hash": source_hash,
            "confirmed_by": confirmed_by,
            "confirmed": memory.confirmed or confirmed_by is not None,
        }
    )


def _source_hash_seed(source_refs: tuple[str, ...]) -> str | None:
    if not source_refs:
        return None
    return "|".join(source_refs)
