from __future__ import annotations

from ai_local.benchmark.metrics import _memory_has_active_evidence, _reciprocal_rank, build_aggregate
from ai_local.benchmark.models import BenchmarkScores, BenchmarkTaskResult


def test_memory_active_evidence_counts_used_memories() -> None:
    result = BenchmarkTaskResult(
        benchmark_id="b",
        run_id="r",
        task_id="mem",
        category="memory",
        result="pass",
        harness_scores=BenchmarkScores(evidence_score=0.5, memory_score=1.0),
        scores=BenchmarkScores(evidence_score=0.5, memory_score=1.0),
        system_score=0.9,
        harness_system_score=0.9,
        used_memories=["mem_a"],
    )
    assert _memory_has_active_evidence(result)


def test_reciprocal_rank_pass_is_one() -> None:
    result = BenchmarkTaskResult(
        benchmark_id="b",
        run_id="r",
        task_id="ret",
        category="retrieval",
        result="pass",
        harness_scores=BenchmarkScores(task_success=1.0, evidence_score=1.0, retrieval_score=1.0),
        scores=BenchmarkScores(task_success=1.0, evidence_score=1.0, retrieval_score=1.0),
        system_score=1.0,
        harness_system_score=1.0,
        retrieved_refs=["docs/a.md"],
    )
    assert _reciprocal_rank(result) == 1.0


def test_aggregate_meets_memory_and_mrr_targets() -> None:
    from ai_local.benchmark.runner import run_golden_benchmark

    report = run_golden_benchmark(tasks_root=__import__("pathlib").Path("golden_tasks"))
    assert report.aggregate.memory_metrics.active_memory_with_evidence >= 0.85
    assert report.aggregate.retrieval_metrics.mrr >= 0.85
    agg = build_aggregate(report.tasks)
    assert agg.retrieval_metrics.mrr >= 0.85
