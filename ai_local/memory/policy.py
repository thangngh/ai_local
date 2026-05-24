from ai_local.memory.layers import MEMORY_LAYER_POLICIES
from ai_local.memory.models import (
    MemoryDecision,
    MemoryItem,
    MemoryRetrievalDecision,
    MemorySqlNoise,
    MemoryWriteDecision,
)


def decide_memory_sql(item: MemoryItem, noise_type: MemorySqlNoise = "none") -> MemoryDecision:
    sql_decisions: dict[MemorySqlNoise, MemoryWriteDecision | MemoryRetrievalDecision] = {
        "none": "accept",
        "scope_noise": "reject_policy_promotion",
        "weak_project_evidence": "verify",
        "wrong_scope": "drop",
        "conflicting_memory": "ask_user",
        "stale_source_hash": "demote",
        "inferred_policy": "ask_user",
        "deep_memory_poisoning": "quarantine",
        "safety_policy_laundering": "stop",
    }
    decision = sql_decisions[noise_type]
    return MemoryDecision(item=item, decision=decision, reason=f"sql noise policy: {noise_type}")


def decide_write(item: MemoryItem) -> MemoryDecision:
    layer = MEMORY_LAYER_POLICIES[item.memory_level]
    if item.secret_like or item.sensitivity == "secret":
        return _write(item, "reject_memory", "secret-like claims are not memory")
    if item.scope not in layer.scopes:
        return _write(item, "reject_memory", "memory scope not allowed for layer")
    if item.memory_level == "M0_SESSION_SCRATCH" and item.inferred_policy:
        return _write(item, "reject_policy_promotion", "session scratch cannot become policy")
    if item.inferred_policy and layer.may_be_policy and not item.confirmed:
        return _write(item, "ask_user", "policy memory requires confirmation")
    if layer.requires_confirmation and not item.confirmed:
        return _write(item, "ask_user", "layer requires confirmed memory")
    if not item.has_explicit_evidence:
        return _write(item, "verify", "memory writes require explicit evidence")
    if item.sensitivity == "sensitive" and not item.confirmed:
        return _write(item, "ask_user", "sensitive memory requires confirmation")
    if item.evidence_strength < layer.min_evidence_strength:
        return _write(item, "verify", "memory evidence below layer threshold")
    return _write(item, "accept_memory", "memory write thresholds passed")


def decide_retrieval(
    item: MemoryItem,
    *,
    requested_scope: str,
    requested_role: str | None = None,
) -> MemoryDecision:
    if item.scope != requested_scope:
        return _retrieval(item, "drop", "wrong-scope memory cannot be injected")
    if requested_role is not None and item.role != requested_role:
        return _retrieval(item, "drop", "wrong-role memory cannot be injected")
    if item.status in {"archived", "quarantined"}:
        return _retrieval(item, "do_not_use", "inactive memory status cannot be injected")
    if item.sensitivity in {"sensitive", "secret"} and not item.confirmed:
        return _retrieval(item, "verify_before_use", "sensitive memory needs confirmation")
    if not item.has_explicit_evidence:
        return _retrieval(item, "verify_before_use", "memory is missing explicit evidence")
    if item.harmful_usage:
        return _retrieval(item, "archive_memory", "harmful usage history archives memory")
    if item.source_hash_changed:
        return _retrieval(item, "demote_stale", "source hash changed")
    if item.conflict_score >= 0.70:
        return _retrieval(item, "do_not_use", "conflicted memory cannot be injected")
    if not item.fresh and item.memory_level in {"M2_PROJECT_CONVENTION", "M4_WORKFLOW_MEMORY"}:
        return _retrieval(item, "verify_before_use", "stale project memory needs verification")
    if item.memory_level == "M4_WORKFLOW_MEMORY" and item.usage_success_rate < 0.50:
        return _retrieval(item, "verify_before_use", "workflow memory lacks success history")
    if item.retrieval_score >= 0.70 and item.risk < 0.50:
        return _retrieval(item, "inject_memory", "retrieval thresholds passed")
    return _retrieval(item, "verify_before_use", "retrieval evidence is not strong enough")


def prefer_confirmed_memory(newer: MemoryItem, older: MemoryItem) -> MemoryDecision:
    if newer.confirmed and not older.confirmed:
        return _retrieval(newer, "prefer_confirmed_memory", "confirmed memory beats inference")
    return _retrieval(newer, "verify_before_use", "confirmation precedence unavailable")


def _write(item: MemoryItem, decision: MemoryWriteDecision, reason: str) -> MemoryDecision:
    return MemoryDecision(item=item, decision=decision, reason=reason)


def _retrieval(
    item: MemoryItem,
    decision: MemoryRetrievalDecision,
    reason: str,
) -> MemoryDecision:
    return MemoryDecision(item=item, decision=decision, reason=reason)
