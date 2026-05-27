from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ai_local.benchmark.metrics import build_aggregate
from ai_local.benchmark.models import BenchmarkRunReport, BenchmarkTaskResult, BenchmarkScores
from ai_local.benchmark.ollama_eval import OllamaBenchmarkConfig
from ai_local.benchmark.replay import render_replay_report, task_attention_flags
from ai_local.benchmark.runner import run_golden_benchmark, write_benchmark_report
from ai_local.cli import app
from ai_local.llm.ollama import OllamaChatResult, OllamaClient
from ai_local.llm.tokens import TokenUsage


def _chat_result(content: str) -> OllamaChatResult:
    usage = TokenUsage(
        input_tokens=50,
        output_tokens=20,
        total_tokens=70,
        input_chars=100,
        output_chars=len(content),
        token_source="ollama_api",
    )
    return OllamaChatResult(content=content, latency_ms=5, model="qwen2.5:0.5b", token_usage=usage)


@patch.object(OllamaClient, "chat")
@patch.object(OllamaClient, "ensure_model")
@patch.object(OllamaClient, "health_check", return_value=True)
def test_ollama_run_exports_three_score_blocks(
    _health: MagicMock,
    _ensure: MagicMock,
    chat: MagicMock,
) -> None:
    chat.return_value = _chat_result(
        "DECISION: continue\nEVIDENCE: ai_local/queue/worker.py\nRATIONALE: ok\n"
    )
    report = run_golden_benchmark(
        tasks_root=Path("golden_tasks"),
        benchmark_id="phase_b_ollama",
        ollama_config=OllamaBenchmarkConfig(),
    )
    assert report.run_mode == "harness+ollama"
    for task in report.tasks:
        assert task.harness_scores is not None
        assert task.llm_scores is not None
        assert task.scores is not None
        assert task.harness_system_score >= 0.0
        assert task.llm_system_score is not None
        assert task.system_score >= 0.0
    assert report.aggregate.llm_system_score is not None


def test_replay_flags_failures_and_low_llm() -> None:
    task = BenchmarkTaskResult(
        benchmark_id="b",
        run_id="r",
        task_id="low_llm_task",
        category="safety",
        result="partial",
        harness_scores=BenchmarkScores(task_success=1.0),
        llm_scores=BenchmarkScores(task_success=0.4),
        scores=BenchmarkScores(task_success=0.7),
        system_score=0.7,
        harness_system_score=1.0,
        llm_system_score=0.55,
        failures=["decision_matches"],
    )
    report = BenchmarkRunReport(
        benchmark_id="b",
        run_id="r",
        generated_at="2026-01-01T00:00:00+00:00",
        run_mode="harness+ollama",
        tasks=[task],
        aggregate=build_aggregate([task]),
    )
    flags = task_attention_flags(task, llm_alert_below=0.70)
    assert "failures:1" in flags
    assert any(item.startswith("low_llm:") for item in flags)
    rendered = render_replay_report(report, llm_alert_below=0.70)
    assert "FLAGS" in rendered
    assert "low_llm_task" in rendered


def test_benchmark_replay_cli_reads_report(tmp_path: Path) -> None:
    report = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="phase_b_cli")
    path = write_benchmark_report(report, tmp_path / "latest.json", append_history=False)
    result = CliRunner().invoke(
        app,
        ["benchmark-replay", "--run", str(path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert report.run_id in result.output
    assert "TASKS" in result.output


def test_written_json_contains_split_score_fields(tmp_path: Path) -> None:
    report = run_golden_benchmark(tasks_root=Path("golden_tasks"), benchmark_id="phase_b_json")
    path = write_benchmark_report(report, tmp_path / "run.json", append_history=False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    task = payload["tasks"][0]
    assert "harness_scores" in task
    assert "scores" in task
    assert "harness_system_score" in task
    assert "harness_system_score" in payload["aggregate"]
    summary_path = tmp_path / f"{report.run_id}_summary.md"
    assert summary_path.exists()
    assert "| harness |" in summary_path.read_text(encoding="utf-8")
