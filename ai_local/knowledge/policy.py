from ai_local.knowledge.models import KnowledgeDecision, KnowledgeGateDecision, KnowledgeItem


def decide_knowledge(item: KnowledgeItem) -> KnowledgeGateDecision:
    if item.noise_type == "prompt_injection":
        return _decision(item, "quarantine", "retrieved knowledge contains prompt injection")
    if item.noise_type == "deep_policy_laundering":
        return _decision(item, "reject", "policy authority was laundered through context")
    if item.level in {"K2_PROJECT", "K3_CURRENT", "K6_DECISION_POLICY"} and not item.all_source_refs:
        return _decision(item, "verify_more", "knowledge claim is missing source references")
    if item.rank >= 75 and not item.evidence_refs:
        return _decision(item, "verify_more", "high-rank knowledge claim is missing evidence refs")
    if item.level == "K3_CURRENT" and not _has_fresh_source(item):
        return _decision(item, "verify_more", "current claim needs a fresh source reference")
    if item.conflict_score >= 0.70:
        return _decision(item, "ask_user", "knowledge evidence conflicts")
    if item.level == "K0_UNKNOWN" or item.rank < 40:
        return _decision(item, "reject", "claim is not evidenced enough to be a fact")
    if item.evidence_strength <= 0.55:
        return _decision(item, "verify_more", "evidence strength below use threshold")
    if item.rank >= 75 and item.confidence >= 0.70 and item.conflict_score <= 0.50:
        return _decision(item, "use", "knowledge score thresholds passed")
    return _decision(item, "verify_more", "knowledge needs stronger evidence")


def _decision(
    item: KnowledgeItem,
    decision: KnowledgeDecision,
    reason: str,
) -> KnowledgeGateDecision:
    return KnowledgeGateDecision(item=item, decision=decision, reason=reason)


def _has_fresh_source(item: KnowledgeItem) -> bool:
    if not item.source_refs:
        return False
    return any(source.observed_at for source in item.source_refs)
