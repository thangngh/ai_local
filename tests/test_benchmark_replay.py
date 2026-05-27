from __future__ import annotations

from pathlib import Path

from ai_local.benchmark.history import append_benchmark_history, load_benchmark_history, render_trend_table
from ai_local.benchmark.replay import format_task_line, load_benchmark_report, render_replay_report
from ai_local.benchmark.runner import run_golden_benchmark, write_benchmark_report
from ai_local.benchmark.summary import render_summary_table, write_summary_markdown
from ai_local.benchmark.thresholds import enforce_thresholds, load_benchmark_thresholds


def test_split_scores_in_report(tmp_path: Path) -> None:
    report = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="split_test")
    assert report.tasks
    first = report.tasks[0]
    assert first.harness_scores is not None
    assert first.harness_system_score >= 0.0
    assert first.scores is not None
    assert report.aggregate.harness_system_score > 0.0


def test_replay_and_summary(tmp_path: Path) -> None:
    report = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="replay_test")
    output = write_benchmark_report(report, tmp_path / "latest.json", append_history=False)
    loaded = load_benchmark_report(output)
    line = format_task_line(loaded.tasks[0])
    assert loaded.run_id in render_replay_report(loaded)
    assert loaded.tasks[0].task_id in line
    summary = render_summary_table(loaded)
    assert "| task_id |" in summary
    summary_path = write_summary_markdown(loaded, tmp_path / "summary.md")
    assert summary_path.exists()


def test_benchmark_history_and_thresholds(tmp_path: Path) -> None:
    report = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="threshold_test")
    history_path = tmp_path / "history.jsonl"
    append_benchmark_history(report, history_path)
    entries = load_benchmark_history(history_path, limit=5)
    assert len(entries) == 1
    assert entries[0].harness_score == report.aggregate.harness_system_score
    trend = render_trend_table(entries)
    assert report.run_id in trend

    thresholds = load_benchmark_thresholds(Path("configs/benchmark_thresholds.yaml"))
    assert enforce_thresholds(report, thresholds) == []

    low_payload = report.model_dump(mode="json")
    low_payload["aggregate"]["harness_system_score"] = 0.1
    low_payload["aggregate"]["system_score"] = 0.1
    from ai_local.benchmark.models import BenchmarkRunReport

    low_report = BenchmarkRunReport.model_validate(low_payload)
    violations = enforce_thresholds(low_report, thresholds)
    assert violations
