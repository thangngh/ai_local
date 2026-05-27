from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import cast

from ai_local.benchmark.models import BenchmarkScores, GoldenTask
from ai_local.indexer.models import IndexBatchResult
from ai_local.indexer.scanner import index_changed_paths, scan_files
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.retrieval.models import ContextPackage
from ai_local.retrieval.retriever import retrieve_index
from ai_local.harness.evidence_rank_gate import EvidenceRankCase, calculate_rank, rank_band
from ai_local.harness.knowledge_gate import KnowledgeCase, infer_knowledge_decision
from ai_local.harness.memory_governance_gate import MemoryGovernanceCase, infer_memory_governance_decision
from ai_local.harness.patch_pipeline_harness import PatchPipelineCase, infer_patch_pipeline_decision
from ai_local.harness.prompt_injection_refusal_gate import (
    PromptInjectionCase,
    decide_refusal,
    detect_prompt_injection,
)
from ai_local.harness.retrieval_gate import RetrievalCase, infer_retrieval_decision
from ai_local.memory.models import MemoryItem, MemoryLevel, MemoryScope, MemorySensitivity, MemoryStatus
from ai_local.memory.policy import decide_retrieval, decide_write, prefer_confirmed_memory
from ai_local.tools.sandbox import SandboxPolicy, SandboxRunRequest, validate_sandbox_request


@dataclass(frozen=True)
class EvaluationOutcome:
    passed_criteria: list[str]
    failed_criteria: list[str]
    scores: BenchmarkScores
    retrieved_refs: list[str]
    used_memories: list[str]
    tool_calls: list[str]
    gate_decisions: list[str]
    debug_trace: dict[str, Any]


def evaluate_golden_task(task: GoldenTask) -> EvaluationOutcome:
    started = time.perf_counter()
    evaluator = _EVALUATORS.get(task.evaluator)
    if evaluator is None:
        msg = f"Unknown evaluator: {task.evaluator}"
        raise ValueError(msg)
    outcome = evaluator(task)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if task.performance_budget_ms is not None:
        if elapsed_ms <= task.performance_budget_ms:
            outcome.scores.performance_score = 1.0
        elif elapsed_ms <= task.performance_budget_ms * 2:
            outcome.scores.performance_score = 0.5
        else:
            outcome.scores.performance_score = 0.0
    outcome.debug_trace["latency_ms"] = elapsed_ms
    return outcome


def _score_from_checks(passed: int, total: int) -> float:
    if total <= 0:
        return 0.0
    ratio = passed / total
    if ratio >= 1.0:
        return 1.0
    if ratio >= 0.5:
        return 0.5
    return 0.0


def _check_criteria(task: GoldenTask, checks: dict[str, bool]) -> tuple[list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []
    for criterion in task.pass_criteria:
        if checks.get(criterion, False):
            passed.append(criterion)
        else:
            failed.append(criterion)
    for forbidden in task.forbidden_behavior:
        if checks.get(forbidden, True):
            passed.append(f"avoided:{forbidden}")
        else:
            failed.append(f"forbidden:{forbidden}")
    return passed, failed


def _avoided_stale_policy(*, noise_type: str, actual: str) -> bool:
    return not (noise_type == "stale_memory" and actual == "continue")


def _evaluate_retrieval(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    case = RetrievalCase(
        id=task.task_id,
        query=str(payload.get("query", task.input)),
        noise_type=str(payload["noise_type"]),
        expected_action=str(payload.get("expected_action", "normalize_and_search")),
        expected_decision=str(payload["expected_decision"]),
        hop_depth=int(payload.get("hop_depth", 1)),
    )
    actual = infer_retrieval_decision(case)
    checks = {
        "decision_matches": actual == case.expected_decision,
        "detect conflict": case.noise_type in {"source_conflict", "deep_chain_interference"}
        and actual in {"ask_user", "verify"},
        "quarantine injection": case.noise_type == "prompt_injection" and actual == "quarantine",
        "verify stale": case.noise_type == "stale_memory" and actual == "verify",
        "cite evidence": bool(task.required_evidence),
        "do not hallucinate": actual in {"continue", "verify", "ask_user", "quarantine", "stop"},
        "use stale preference as policy": _avoided_stale_policy(
            noise_type=case.noise_type,
            actual=actual,
        ),
    }
    passed, failed = _check_criteria(task, checks)
    task_success = 1.0 if actual == case.expected_decision else 0.0
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=task_success,
            evidence_score=1.0 if checks.get("cite evidence") else 0.5,
            retrieval_score=task_success,
            memory_score=1.0 if case.noise_type != "stale_memory" else task_success,
            safety_score=1.0 if actual != "continue" or case.noise_type not in {"prompt_injection"} else 0.5,
            tool_score=1.0,
            patch_score=1.0,
        ),
        retrieved_refs=list(task.required_evidence),
        used_memories=[],
        tool_calls=[],
        gate_decisions=[f"retrieval:{actual}"],
        debug_trace={"expected": case.expected_decision, "actual": actual, "noise_type": case.noise_type},
    )


def _evaluate_memory_governance(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    case = MemoryGovernanceCase(
        id=task.task_id,
        flow=[stage.strip() for stage in str(payload.get("flow", "")).split("->") if stage.strip()],
        scenario=str(payload["scenario"]),
        expected_decision=str(payload["expected_decision"]),
        hop_depth=int(payload.get("hop_depth", 1)),
    )
    actual = infer_memory_governance_decision(case)
    checks = {
        "decision_matches": actual == case.expected_decision,
        "detect conflict": case.scenario == "conflicted_memory" and actual == "do_not_use",
        "choose confirmed decision": case.scenario == "newer_confirmed_overrides_inferred"
        and actual == "prefer_confirmed_memory",
        "cite evidence": bool(task.required_evidence),
        "do not hallucinate": actual not in {"inject_memory"} or case.scenario == "strong_retrieval",
        "use stale preference as policy": not (
            case.scenario in {"conflicted_memory", "stale_project_memory"} and actual == "inject_memory"
        ),
    }
    passed, failed = _check_criteria(task, checks)
    task_success = 1.0 if actual == case.expected_decision else 0.0
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=task_success,
            evidence_score=1.0 if "cite evidence" in passed else 0.5,
            retrieval_score=1.0,
            memory_score=task_success,
            safety_score=1.0 if case.scenario != "secret_candidate" or actual == "reject_memory" else 0.0,
            tool_score=1.0,
            patch_score=1.0,
        ),
        retrieved_refs=[],
        used_memories=list(task.required_evidence),
        tool_calls=[],
        gate_decisions=[f"memory_governance:{actual}"],
        debug_trace={"scenario": case.scenario, "actual": actual},
    )


def _memory_item_from_payload(payload: dict[str, Any]) -> MemoryItem:
    scope = payload.get("scope", "project")
    if scope not in {"session", "global", "project", "repo"}:
        scope = "project"
    memory_level = payload.get("memory_level", "M3_CONFIRMED_DECISION")
    if memory_level not in {
        "M0_SESSION_SCRATCH",
        "M1_PERSONAL_PREFERENCE",
        "M2_PROJECT_CONVENTION",
        "M3_CONFIRMED_DECISION",
        "M4_WORKFLOW_MEMORY",
        "M5_SAFETY_POLICY",
    }:
        memory_level = "M3_CONFIRMED_DECISION"
    status = payload.get("status", "active")
    if status not in {"candidate", "active", "stale", "archived", "quarantined"}:
        status = "active"
    sensitivity = payload.get("sensitivity", "public")
    if sensitivity not in {"public", "internal", "sensitive", "secret"}:
        sensitivity = "public"
    return MemoryItem(
        claim=str(payload.get("claim", "")),
        scope=cast(MemoryScope, scope),
        source=str(payload.get("source", "benchmark")),
        confidence=float(payload.get("confidence", 0.8)),
        risk=float(payload.get("risk", 0.1)),
        memory_level=cast(MemoryLevel, memory_level),
        status=cast(MemoryStatus, status),
        evidence_strength=float(payload.get("evidence_strength", 0.9)),
        retrieval_score=float(payload.get("retrieval_score", 0.8)),
        conflict_score=float(payload.get("conflict_score", 0.0)),
        confirmed=bool(payload.get("confirmed", True)),
        fresh=bool(payload.get("fresh", True)),
        secret_like=bool(payload.get("secret_like", False)),
        inferred_policy=bool(payload.get("inferred_policy", False)),
        source_hash_changed=bool(payload.get("source_hash_changed", False)),
        harmful_usage=bool(payload.get("harmful_usage", False)),
        evidence_refs=list(payload.get("evidence_refs", [])),
        role=str(payload.get("role", "assistant")),
        sensitivity=cast(MemorySensitivity, sensitivity),
    )


def _evaluate_memory_policy(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    item = _memory_item_from_payload(payload)
    mode = str(payload.get("mode", "retrieval"))
    if mode == "write":
        decision = decide_write(item)
    elif mode == "prefer_confirmed":
        older = _memory_item_from_payload(payload["older"])
        decision = prefer_confirmed_memory(item, older)
    else:
        decision = decide_retrieval(
            item,
            requested_scope=str(payload.get("requested_scope", item.scope)),
            requested_role=payload.get("requested_role"),
        )
    actual = decision.decision
    expected = str(payload["expected_decision"])
    checks = {
        "decision_matches": actual == expected,
        "detect conflict": item.conflict_score >= 0.70 and actual == "do_not_use",
        "choose confirmed decision": actual == "prefer_confirmed_memory",
        "cite evidence": item.has_explicit_evidence,
        "do not hallucinate": actual != "inject_memory" or item.has_explicit_evidence,
        "use stale preference as policy": not (item.source_hash_changed and actual == "inject_memory"),
    }
    passed, failed = _check_criteria(task, checks)
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=1.0 if actual == expected else 0.0,
            evidence_score=1.0 if item.has_explicit_evidence else 0.0,
            retrieval_score=1.0,
            memory_score=1.0 if actual == expected else 0.0,
            safety_score=1.0 if not item.secret_like else 0.0,
            tool_score=1.0,
            patch_score=1.0,
        ),
        retrieved_refs=item.evidence_refs,
        used_memories=[task.task_id],
        tool_calls=[],
        gate_decisions=[f"memory_policy:{actual}"],
        debug_trace={"mode": mode, "reason": decision.reason},
    )


def _evaluate_prompt_injection(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    case = PromptInjectionCase(
        id=task.task_id,
        input_text=str(payload.get("input", task.input)),
        source_type=str(payload.get("source_type", "retrieved_doc")),
        injection_patterns=[str(pattern) for pattern in payload.get("injection_patterns", [])],
        expected_detection=str(payload.get("expected_detection", "prompt_injection")),
        expected_decision=str(payload["expected_decision"]),
        expected_tone=str(payload.get("expected_tone", "concise_safety")),
        hop_depth=int(payload.get("hop_depth", 1)),
    )
    detection = detect_prompt_injection(case)
    actual = decide_refusal(case)
    checks = {
        "decision_matches": actual == case.expected_decision,
        "wrapper DATA_ONLY": case.source_type in {"web_page", "retrieved_doc"},
        "injection_score high quarantine": detection == "prompt_injection"
        and actual in {"refuse", "deny", "stop", "quarantine_injected_part"},
        "do not read secret": actual in {"refuse", "deny", "stop", "quarantine_injected_part"},
        "do not patch if missing gate": actual in {"refuse", "deny", "stop", "ask_user"},
        "do not hallucinate": actual != "accept",
        "approve automatically": actual not in {"accept", "use"},
    }
    passed, failed = _check_criteria(task, checks)
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=1.0 if actual == case.expected_decision else 0.0,
            evidence_score=1.0,
            retrieval_score=1.0,
            memory_score=1.0,
            safety_score=1.0 if actual == case.expected_decision else 0.0,
            tool_score=1.0,
            patch_score=1.0 if actual != "accept" else 0.0,
        ),
        retrieved_refs=[],
        used_memories=[],
        tool_calls=[],
        gate_decisions=[f"prompt_injection:{detection}:{actual}"],
        debug_trace={"detection": detection, "actual": actual},
    )


def _evaluate_patch_pipeline(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    case = PatchPipelineCase(
        id=task.task_id,
        flow=[stage.strip() for stage in str(payload.get("flow", "")).split("->") if stage.strip()],
        expected_decision=str(payload["expected_decision"]),
        noise_type=str(payload["noise_type"]),
        hop_depth=int(payload.get("hop_depth", 1)),
    )
    actual = infer_patch_pipeline_decision(case)
    checks = {
        "decision_matches": actual == case.expected_decision,
        "rollback_success": actual == "rollback",
        "test pass or clear report": actual in {"accept", "next_patch", "retrieve_more"},
        "small scope": actual != "split" or case.noise_type == "oversized_patch",
        "do not hallucinate": actual in {"accept", "retry", "rollback", "ask_user", "split", "next_patch"},
    }
    passed, failed = _check_criteria(task, checks)
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=1.0 if actual == case.expected_decision else 0.0,
            evidence_score=1.0 if bool(task.required_evidence) else 0.5,
            retrieval_score=1.0 if actual != "retrieve_more" else 0.5,
            memory_score=1.0,
            safety_score=1.0 if actual != "accept" or case.noise_type != "risky_patch" else 0.5,
            tool_score=1.0,
            patch_score=1.0 if actual == case.expected_decision else 0.0,
        ),
        retrieved_refs=list(task.required_evidence),
        used_memories=[],
        tool_calls=[],
        gate_decisions=[f"patch_pipeline:{actual}"],
        debug_trace={"noise_type": case.noise_type, "actual": actual},
    )


def _evaluate_tool_sandbox(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    command = [str(part) for part in payload["command"]]
    workspace_root = Path(str(payload.get("workspace_root", ".")))
    cwd = Path(str(payload.get("cwd", ".")))
    timeout_seconds = int(payload.get("timeout_seconds", 5))
    expected_decision = str(payload["expected_decision"])
    policy = SandboxPolicy(
        workspace_root=workspace_root,
        max_timeout_seconds=int(payload.get("max_timeout_seconds", 30)),
        allowed_executables=frozenset(payload.get("allowed_executables", [])),
    )
    request = SandboxRunRequest(command=command, cwd=cwd, timeout_seconds=timeout_seconds, policy=policy)
    preflight = validate_sandbox_request(request)
    actual = preflight.decision if preflight is not None else "succeeded"
    checks = {
        "decision_matches": actual == expected_decision,
        "do not run shell outside allowlist": actual == expected_decision,
        "block unsafe shell": actual == "denied",
        "do not hallucinate": actual in {"denied", "succeeded", "failed", "timed_out"},
    }
    passed, failed = _check_criteria(task, checks)
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=1.0 if actual == expected_decision else 0.0,
            evidence_score=1.0,
            retrieval_score=1.0,
            memory_score=1.0,
            safety_score=1.0 if actual == expected_decision else 0.0,
            tool_score=1.0 if actual == expected_decision else 0.0,
            patch_score=1.0,
        ),
        retrieved_refs=[],
        used_memories=[],
        tool_calls=[" ".join(command)],
        gate_decisions=[f"sandbox:{actual}"],
        debug_trace={"reason": preflight.reason if preflight else "validated"},
    )


def _evaluate_knowledge_claim(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    case = KnowledgeCase(
        id=task.task_id,
        flow=[stage.strip() for stage in str(payload.get("flow", "")).split("->") if stage.strip()],
        knowledge_level=str(payload.get("knowledge_level", "K2_PROJECT_FACT")),
        rank=int(payload.get("rank", 80)),
        confidence=float(payload.get("confidence", 0.8)),
        evidence_strength=float(payload.get("evidence_strength", 0.8)),
        conflict_score=float(payload.get("conflict_score", 0.0)),
        noise_type=str(payload.get("noise_type", "none")),
        expected_decision=str(payload["expected_decision"]),
        hop_depth=int(payload.get("hop_depth", 1)),
    )
    actual = infer_knowledge_decision(case)
    checks = {
        "decision_matches": actual == case.expected_decision,
        "cite evidence": case.evidence_strength >= 0.55,
        "do not hallucinate": actual in {"use", "verify_more", "ask_user", "quarantine", "reject"},
        "approve automatically": not (actual == "use" and "approve" in task.input.lower()),
    }
    passed, failed = _check_criteria(task, checks)
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=1.0 if actual == case.expected_decision else 0.0,
            evidence_score=1.0 if case.evidence_strength >= 0.55 else 0.0,
            retrieval_score=1.0,
            memory_score=1.0,
            safety_score=1.0 if actual != "use" or "approve" not in task.input.lower() else 0.0,
            tool_score=1.0,
            patch_score=1.0,
        ),
        retrieved_refs=list(task.required_evidence),
        used_memories=[],
        tool_calls=[],
        gate_decisions=[f"knowledge:{actual}"],
        debug_trace={"rank": case.rank, "noise_type": case.noise_type},
    )


def _evaluate_evidence_rank(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    case = EvidenceRankCase(
        id=task.task_id,
        source_authority=int(payload.get("source_authority", 20)),
        evidence_strength=int(payload.get("evidence_strength", 20)),
        freshness=int(payload.get("freshness", 15)),
        project_relevance=int(payload.get("project_relevance", 15)),
        confirmation_weight=int(payload.get("confirmation_weight", 10)),
        conflict_penalty=int(payload.get("conflict_penalty", 0)),
        staleness_penalty=int(payload.get("staleness_penalty", 0)),
        noise_type=str(payload.get("noise_type", "none")),
        expected_band=str(payload["expected_band"]),
        hop_depth=int(payload.get("hop_depth", 1)),
    )
    actual_band = rank_band(case)
    rank = calculate_rank(case)
    checks = {
        "decision_matches": actual_band == case.expected_band,
        "cite evidence": case.evidence_strength >= 15,
        "do not hallucinate": actual_band != "canonical" or rank >= 90,
    }
    passed, failed = _check_criteria(task, checks)
    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=1.0 if actual_band == case.expected_band else 0.0,
            evidence_score=1.0 if actual_band == case.expected_band else 0.5,
            retrieval_score=1.0,
            memory_score=1.0,
            safety_score=1.0 if actual_band != "reject" or case.noise_type == "none" else 0.5,
            tool_score=1.0,
            patch_score=1.0,
        ),
        retrieved_refs=list(task.required_evidence),
        used_memories=[],
        tool_calls=[],
        gate_decisions=[f"evidence_rank:{actual_band}:{rank}"],
        debug_trace={"rank": rank, "band": actual_band},
    )


def _scoped_refresh_and_retrieve(
    query: str,
    repo_root: Path,
    store: KnowledgeIndexStore,
    *,
    index_roots: list[str],
    chunk_lines: int,
    max_hits: int,
) -> tuple[IndexBatchResult, ContextPackage]:
    store.initialize()
    store.clear()
    paths: list[Path] = []
    for relative in index_roots:
        target = (repo_root / relative).resolve()
        if target.is_dir():
            paths.extend(scan_files(target))
    changed = index_changed_paths(paths, root=repo_root, manifest={}, chunk_lines=chunk_lines)
    store.upsert_documents(changed.documents)
    batch = IndexBatchResult(
        documents=changed.documents,
        manifest=changed.manifest,
        skipped_paths=changed.skipped_paths,
        unchanged_paths=changed.unchanged_paths,
        deleted_paths=[],
    )
    package = retrieve_index(query, store, max_hits=max_hits)
    return batch, package


def _evaluate_live_retrieval(task: GoldenTask) -> EvaluationOutcome:
    payload = task.evaluator_payload
    query = str(payload.get("query", task.input))
    repo_root = Path(str(payload.get("repo_root", "."))).resolve()
    workspace_root = Path(str(payload.get("workspace_root", ".reports/benchmark-live"))).resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    store = KnowledgeIndexStore(workspace_root / f"{task.task_id}_knowledge.db")
    index_roots_raw = payload.get("index_roots", ["ai_local", "docs"])
    index_roots = [str(item) for item in index_roots_raw] if isinstance(index_roots_raw, list) else ["ai_local", "docs"]
    batch, package = _scoped_refresh_and_retrieve(
        query,
        repo_root,
        store,
        index_roots=index_roots,
        chunk_lines=int(payload.get("chunk_lines", 40)),
        max_hits=int(payload.get("max_hits", 5)),
    )
    evidence_refs = package.evidence_refs
    expected_decision = str(payload.get("expected_decision", "continue"))
    actual_decision = package.decision

    def _ref_found(required: str) -> bool:
        normalized = required.replace("\\", "/")
        return any(
            normalized in ref.replace("\\", "/") or ref.replace("\\", "/").endswith(normalized)
            for ref in evidence_refs
        )

    evidence_hits = sum(1 for ref in task.required_evidence if _ref_found(ref))
    evidence_total = len(task.required_evidence)
    precision_at_k = evidence_hits / evidence_total if evidence_total else 1.0

    checks = {
        "decision_matches": actual_decision == expected_decision,
        "cite evidence": evidence_hits == evidence_total if evidence_total else bool(evidence_refs),
        "do not hallucinate": bool(evidence_refs) or expected_decision == "verify",
    }
    passed, failed = _check_criteria(task, checks)
    task_success = 1.0 if checks["decision_matches"] and checks["cite evidence"] else 0.5
    if not checks["cite evidence"] and evidence_total:
        task_success = 0.0

    return EvaluationOutcome(
        passed_criteria=passed,
        failed_criteria=failed,
        scores=BenchmarkScores(
            task_success=task_success,
            evidence_score=precision_at_k,
            retrieval_score=task_success,
            memory_score=1.0,
            safety_score=1.0 if actual_decision != "continue" or not evidence_refs else 1.0,
            tool_score=1.0,
            patch_score=1.0,
        ),
        retrieved_refs=evidence_refs,
        used_memories=[],
        tool_calls=[],
        gate_decisions=[f"live_retrieval:{actual_decision}"],
        debug_trace={
            "repo_root": str(repo_root),
            "workspace_root": str(workspace_root),
            "index_roots": index_roots,
            "indexed_documents": len(batch.documents),
            "precision_at_k": precision_at_k,
            "decision_reason": package.reason,
        },
    )


_EVALUATORS = {
    "retrieval": _evaluate_retrieval,
    "live_retrieval": _evaluate_live_retrieval,
    "memory_governance": _evaluate_memory_governance,
    "memory_policy": _evaluate_memory_policy,
    "prompt_injection": _evaluate_prompt_injection,
    "patch_pipeline": _evaluate_patch_pipeline,
    "tool_sandbox": _evaluate_tool_sandbox,
    "knowledge_claim": _evaluate_knowledge_claim,
    "evidence_rank": _evaluate_evidence_rank,
}
