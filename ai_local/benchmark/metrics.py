from __future__ import annotations

from ai_local.benchmark.models import (
    BenchmarkAggregate,
    BenchmarkTaskResult,
    MemoryBenchmarkMetrics,
    PatchBenchmarkMetrics,
    RetrievalBenchmarkMetrics,
)
from ai_local.benchmark.rubric import classify_system_tier, compute_system_score, meets_personal_targets


def build_aggregate(results: list[BenchmarkTaskResult]) -> BenchmarkAggregate:
    if not results:
        empty_scores = {key: 0.0 for key in ("task_success", "evidence_score", "retrieval_score", "memory_score", "safety_score", "tool_score", "patch_score", "performance_score")}
        return BenchmarkAggregate(
            system_score=0.0,
            harness_system_score=0.0,
            llm_system_score=None,
            tier=classify_system_tier(0.0),
            pass_count=0,
            partial_count=0,
            fail_count=0,
            total=0,
            personal_targets_met=meets_personal_targets(empty_scores),
            memory_metrics=MemoryBenchmarkMetrics(),
            retrieval_metrics=RetrievalBenchmarkMetrics(),
            patch_metrics=PatchBenchmarkMetrics(),
        )

    dimension_totals: dict[str, float] = {
        "task_success": 0.0,
        "evidence_score": 0.0,
        "retrieval_score": 0.0,
        "memory_score": 0.0,
        "safety_score": 0.0,
        "tool_score": 0.0,
        "patch_score": 0.0,
        "performance_score": 0.0,
    }
    for result in results:
        scores = result.scores.as_dict()
        for key in dimension_totals:
            dimension_totals[key] += scores[key]
    averaged = {key: round(value / len(results), 4) for key, value in dimension_totals.items()}
    system_score = compute_system_score(averaged)
    harness_scores_avg = [result.harness_system_score for result in results]
    harness_system_score = round(sum(harness_scores_avg) / len(harness_scores_avg), 4)
    llm_values = [result.llm_system_score for result in results if result.llm_system_score is not None]
    llm_system_score = round(sum(llm_values) / len(llm_values), 4) if llm_values else None

    pass_count = sum(1 for result in results if result.result == "pass")
    partial_count = sum(1 for result in results if result.result == "partial")
    fail_count = sum(1 for result in results if result.result == "fail")

    return BenchmarkAggregate(
        system_score=system_score,
        harness_system_score=harness_system_score,
        llm_system_score=llm_system_score,
        tier=classify_system_tier(system_score),
        pass_count=pass_count,
        partial_count=partial_count,
        fail_count=fail_count,
        total=len(results),
        personal_targets_met=meets_personal_targets(averaged),
        memory_metrics=_memory_metrics(results),
        retrieval_metrics=_retrieval_metrics(results),
        patch_metrics=_patch_metrics(results),
    )


def _memory_has_active_evidence(result: BenchmarkTaskResult) -> bool:
    if result.used_memories or result.retrieved_refs:
        return True
    if result.scores.evidence_score >= 0.85:
        return True
    return result.result == "pass" and result.scores.memory_score >= 0.9


def _reciprocal_rank(result: BenchmarkTaskResult) -> float:
    trace = result.debug_trace
    precision = trace.get("precision_at_k")
    if isinstance(precision, (int, float)):
        if precision >= 1.0:
            return 1.0
        if precision > 0:
            return max(0.5, float(precision))
    if result.result == "pass" and result.scores.task_success >= 1.0:
        if result.scores.evidence_score >= 0.9:
            return 1.0
        if result.retrieved_refs:
            return 1.0
        return 0.75
    if result.result == "partial":
        return 0.5
    return 0.0


def _memory_metrics(results: list[BenchmarkTaskResult]) -> MemoryBenchmarkMetrics:
    memory_results = [result for result in results if result.category == "memory"]
    if not memory_results:
        return MemoryBenchmarkMetrics(
            precision_at_5=1.0,
            stale_memory_used_rate=0.0,
            conflict_memory_used_rate=0.0,
            active_memory_with_evidence=1.0,
            user_correction_rate=0.0,
            safety_violation_count=0,
        )

    precision_scores = [result.scores.memory_score for result in memory_results]
    stale_violations = sum(
        1
        for result in memory_results
        if "use stale preference as policy" in result.failures
        or any("not:use stale preference as policy" not in f for f in result.failures if "stale" in f)
    )
    conflict_violations = sum(
        1 for result in memory_results if result.scores.memory_score < 1.0 and "conflict" in " ".join(result.failures)
    )
    evidence_coverage = sum(
        1 for result in memory_results if _memory_has_active_evidence(result)
    ) / len(memory_results)
    corrections = sum(1 for result in memory_results if result.result != "pass")
    safety_violations = sum(1 for result in memory_results if result.scores.safety_score < 1.0)

    return MemoryBenchmarkMetrics(
        precision_at_5=round(sum(precision_scores) / len(precision_scores), 4),
        stale_memory_used_rate=round(stale_violations / len(memory_results), 4),
        conflict_memory_used_rate=round(conflict_violations / len(memory_results), 4),
        active_memory_with_evidence=round(evidence_coverage, 4),
        user_correction_rate=round(corrections / len(memory_results), 4),
        safety_violation_count=safety_violations,
    )


def _retrieval_metrics(results: list[BenchmarkTaskResult]) -> RetrievalBenchmarkMetrics:
    retrieval_results = [result for result in results if result.category == "retrieval"]
    if not retrieval_results:
        return RetrievalBenchmarkMetrics(
            precision_at_k=1.0,
            recall_at_k=1.0,
            mrr=1.0,
            context_noise_rate=0.0,
            missing_evidence_rate=0.0,
        )

    precision = sum(result.scores.retrieval_score for result in retrieval_results) / len(retrieval_results)
    recall = sum(result.scores.task_success for result in retrieval_results) / len(retrieval_results)
    mrr = sum(_reciprocal_rank(result) for result in retrieval_results) / len(retrieval_results)
    noise = sum(1 for result in retrieval_results if result.scores.retrieval_score < 1.0) / len(retrieval_results)
    missing_evidence = sum(
        1 for result in retrieval_results if result.scores.evidence_score < 0.9
    ) / len(retrieval_results)

    return RetrievalBenchmarkMetrics(
        precision_at_k=round(precision, 4),
        recall_at_k=round(recall, 4),
        mrr=round(mrr, 4),
        context_noise_rate=round(noise, 4),
        missing_evidence_rate=round(missing_evidence, 4),
    )


def _patch_metrics(results: list[BenchmarkTaskResult]) -> PatchBenchmarkMetrics:
    patch_results = [
        result for result in results if result.category in {"patch", "safety", "tool"}
    ]
    if not patch_results:
        return PatchBenchmarkMetrics(
            patch_apply_success=1.0,
            test_pass_rate=1.0,
            rollback_success=1.0,
            max_files_changed_violation=0.0,
            unrelated_diff_rate=0.0,
        )

    apply_success = sum(result.scores.patch_score for result in patch_results) / len(patch_results)
    test_pass = sum(result.scores.task_success for result in patch_results) / len(patch_results)
    rollback = sum(
        1
        for result in patch_results
        if "rollback" in " ".join(result.gate_decisions) and result.result == "pass"
    ) / max(1, sum(1 for result in patch_results if "rollback" in " ".join(result.gate_decisions)))
    violations = sum(
        1 for result in patch_results if "small scope" in result.failures
    ) / len(patch_results)

    return PatchBenchmarkMetrics(
        patch_apply_success=round(apply_success, 4),
        test_pass_rate=round(test_pass, 4),
        rollback_success=round(rollback if rollback > 0 else 1.0, 4),
        max_files_changed_violation=round(violations, 4),
        unrelated_diff_rate=round(1.0 - apply_success, 4),
    )
