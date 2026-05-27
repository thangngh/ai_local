from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_local.benchmark.evaluators import evaluate_golden_task
from ai_local.benchmark.models import GoldenTask
from ai_local.benchmark.rubric import classify_system_tier, compute_system_score
from ai_local.benchmark.runner import discover_golden_tasks, run_golden_benchmark, write_benchmark_report


def test_discover_minimum_twenty_golden_tasks() -> None:
    tasks = discover_golden_tasks(Path("golden_tasks"))
    assert len(tasks) >= 20
    categories = {task.category for task in tasks}
    assert "retrieval" in categories
    assert "memory" in categories
    assert "safety" in categories
    assert "patch" in categories


def test_memory_conflict_task_prefers_confirmed_decision() -> None:
    payload = json.loads(Path("golden_tasks/memory_conflict_resolution/task.json").read_text(encoding="utf-8"))
    task = GoldenTask.model_validate(payload)
    outcome = evaluate_golden_task(task)
    assert outcome.scores.task_success == 1.0
    assert "memory_governance:prefer_confirmed_memory" in outcome.gate_decisions


def test_run_golden_benchmark_produces_passing_report(tmp_path: Path) -> None:
    report = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="test_bench")
    assert report.aggregate.total >= 20
    assert report.aggregate.system_score >= 0.85
    assert report.aggregate.fail_count == 0
    output = write_benchmark_report(report, tmp_path / "report.json")
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["aggregate"]["tier"] == classify_system_tier(payload["aggregate"]["system_score"])


def test_system_score_weights() -> None:
    scores = {
        "task_success": 1.0,
        "evidence_score": 1.0,
        "retrieval_score": 1.0,
        "memory_score": 1.0,
        "safety_score": 1.0,
        "tool_score": 1.0,
        "patch_score": 1.0,
        "performance_score": 1.0,
    }
    assert compute_system_score(scores) == 1.0


@pytest.mark.parametrize(
    ("score", "tier_prefix"),
    [
        (0.55, "toy"),
        (0.70, "usable"),
        (0.80, "decent"),
        (0.88, "strong"),
        (0.94, "production"),
    ],
)
def test_tier_classification(score: float, tier_prefix: str) -> None:
    assert classify_system_tier(score).startswith(tier_prefix)
