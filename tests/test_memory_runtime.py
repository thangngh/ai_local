from ai_local.memory.layers import MEMORY_LAYER_POLICIES
from ai_local.memory.models import (
    MemoryConflictRecord,
    MemoryDocMatchSignal,
    MemoryEvidenceRecord,
    MemoryItem,
    MemoryUsageRecord,
)
from ai_local.memory.policy import (
    decide_memory_sql,
    decide_retrieval,
    decide_write,
    prefer_confirmed_memory,
)
from ai_local.memory.regression import evaluate_regression
from ai_local.memory.schema import MEMORY_SCHEMA_COLUMNS, schema_has_columns, schema_has_tables
from ai_local.memory.store import InMemoryMemoryStore


def _memory(**overrides: object) -> MemoryItem:
    item = MemoryItem(
        claim="Use focused memory evidence.",
        scope="project",
        source="docs/requirements.md",
        confidence=0.9,
        memory_level="M2_PROJECT_CONVENTION",
        evidence_strength=0.8,
        retrieval_score=0.9,
        usage_success_rate=0.8,
        status="active",
        evidence_refs=["docs/requirements.md#memory"],
        confirmed_by="user:lead",
        role="assistant",
        source_hash="abc123",
    )
    return item.model_copy(update=overrides)


def _doc_match(**overrides: object) -> MemoryDocMatchSignal:
    signal = MemoryDocMatchSignal(
        semantic_match=0.9,
        flow_match=0.9,
        evidence_match=0.9,
        scope_match=0.9,
    )
    return signal.model_copy(update=overrides)


def test_memory_layers_and_schema_contract_cover_sprint_tables() -> None:
    assert not MEMORY_LAYER_POLICIES["M0_SESSION_SCRATCH"].inject_as_fact
    assert MEMORY_LAYER_POLICIES["M5_SAFETY_POLICY"].requires_confirmation
    assert schema_has_tables(
        [
            "memory_items",
            "memory_evidence",
            "memory_conflicts",
            "memory_updates",
            "memory_usage",
        ]
    )
    assert "expires_at" in MEMORY_SCHEMA_COLUMNS["memory_items"]
    assert schema_has_columns(
        "memory_items",
        ["source_hash", "role", "sensitivity", "confirmed_by"],
    )


def test_memory_write_and_sql_policy_cover_safety_evidence_and_noise() -> None:
    assert decide_write(_memory()).decision == "accept_memory"
    assert decide_write(_memory(secret_like=True)).decision == "reject_memory"
    assert decide_write(_memory(evidence_refs=[], confirmed_by=None)).decision == "verify"
    assert decide_write(_memory(sensitivity="sensitive", confirmed=False)).decision == "ask_user"
    assert decide_write(_memory(evidence_strength=0.2)).decision == "verify"
    assert decide_write(
        _memory(memory_level="M5_SAFETY_POLICY", inferred_policy=True, confirmed=False)
    ).decision == "ask_user"
    assert decide_memory_sql(_memory(), "deep_memory_poisoning").decision == "quarantine"
    assert decide_memory_sql(_memory(), "safety_policy_laundering").decision == "stop"


def test_memory_retrieval_governance_drops_conflicts_demotes_and_prefers_confirmation() -> None:
    assert decide_retrieval(_memory(), requested_scope="project").decision == "inject_memory"
    assert decide_retrieval(_memory(), requested_scope="repo").decision == "drop"
    assert decide_retrieval(
        _memory(role="developer"),
        requested_scope="project",
        requested_role="assistant",
    ).decision == "drop"
    assert decide_retrieval(
        _memory(evidence_refs=[], confirmed_by=None),
        requested_scope="project",
    ).decision == "verify_before_use"
    assert decide_retrieval(_memory(fresh=False), requested_scope="project").decision == (
        "verify_before_use"
    )
    assert decide_retrieval(_memory(conflict_score=0.8), requested_scope="project").decision == (
        "do_not_use"
    )
    assert decide_retrieval(
        _memory(source_hash_changed=True),
        requested_scope="project",
    ).decision == "demote_stale"
    assert prefer_confirmed_memory(
        _memory(memory_level="M3_CONFIRMED_DECISION", confirmed=True),
        _memory(memory_level="M3_CONFIRMED_DECISION", confirmed=False),
    ).decision == "prefer_confirmed_memory"


def test_memory_store_tracks_evidence_conflicts_and_usage_records() -> None:
    store = InMemoryMemoryStore()
    item = _memory()
    store.add(item)
    store.add_evidence(
        MemoryEvidenceRecord(
            memory_id="mem-1",
            evidence_type="project_doc",
            ref="docs/requirements.md",
            weight=0.8,
        )
    )
    store.add_conflict(
        MemoryConflictRecord(
            memory_id="mem-1",
            conflicting_memory_id="mem-2",
            conflict_score=0.8,
            reason="conflicting project convention",
        )
    )
    store.add_usage(
        MemoryUsageRecord(
            memory_id="mem-1",
            run_id="run-1",
            retrieval_score=0.9,
            used_as="context",
            outcome="success",
        )
    )

    assert len(store.active("project")) == 1
    assert len(store.evidence_for("mem-1")) == 1
    assert len(store.open_conflicts_for("mem-1")) == 1
    assert len(store.usage_for("mem-1")) == 1


def test_memory_regression_restores_state_and_protects_doc_match() -> None:
    restored = evaluate_regression(
        pattern="a-b-c-d-c",
        signal=_doc_match(),
        constraints_restored=2,
        constraints_required=2,
    )
    conflict = evaluate_regression(
        pattern="a-b-c-e-c",
        signal=_doc_match(conflicted=True),
        constraints_restored=2,
        constraints_required=2,
    )
    laundered = evaluate_regression(
        pattern="a-b-c-d-c-a",
        signal=_doc_match(laundered=True),
        constraints_restored=3,
        constraints_required=3,
    )
    missing_constraints = evaluate_regression(
        pattern="a-b-c-d",
        signal=_doc_match(),
        constraints_restored=1,
        constraints_required=2,
    )

    assert (restored.active_state, restored.state_hops, restored.decision) == ("c", 4, "restore")
    assert conflict.decision == "verify_before_use"
    assert laundered.decision == "reject_laundered_match"
    assert missing_constraints.decision == "verify_before_use"
