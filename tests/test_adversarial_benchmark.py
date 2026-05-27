from __future__ import annotations

from pathlib import Path

from ai_local.benchmark.runner import discover_benchmark_tasks, discover_golden_tasks, run_golden_benchmark


def test_discover_golden_excludes_adversarial() -> None:
    golden = discover_golden_tasks(Path("golden_tasks"))
    all_with_adv = discover_benchmark_tasks(Path("golden_tasks"), include_adversarial=True)
    assert len(golden) == 22
    assert len(all_with_adv) >= 30
    assert len(all_with_adv) == len(golden) + 10
    golden_ids = {task.task_id for task in golden}
    adv_ids = {task.task_id for task in all_with_adv} - golden_ids
    assert len(adv_ids) == 10
    assert all(task_id.startswith("adv_") for task_id in adv_ids)


def test_run_with_adversarial_includes_adv_tasks() -> None:
    report = run_golden_benchmark(
        tasks_root=Path("golden_tasks"),
        benchmark_id="test_adv",
        include_adversarial=True,
    )
    assert report.aggregate.total >= 30
    adv_tasks = [task for task in report.tasks if task.task_id.startswith("adv_")]
    assert len(adv_tasks) == 10
