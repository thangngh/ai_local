from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.pipeline.stress import load_phase9_stress_cases, run_phase9_stress_cases


ROOT = Path(__file__).resolve().parents[1]


def test_phase9_stress_cases_cover_retriever_queue_and_timeout() -> None:
    cases = load_phase9_stress_cases(ROOT / "configs" / "phase9_stress_gates.yaml")

    assert [case.kind for case in cases] == ["retriever", "queue", "worker_timeout"]
    assert max(case.hop_depth for case in cases) == 50


def test_phase9_stress_runner_passes_configured_cases(tmp_path: Path) -> None:
    results = run_phase9_stress_cases(
        config_path=ROOT / "configs" / "phase9_stress_gates.yaml",
        workspace_root=tmp_path / "stress",
    )

    assert all(result.passed for result in results)
    retriever = next(result for result in results if result.kind == "retriever")
    queue = next(result for result in results if result.kind == "queue")
    timeout = next(result for result in results if result.kind == "worker_timeout")
    assert retriever.metrics["first_indexed"] == 32
    assert retriever.metrics["second_unchanged"] == 32
    assert queue.metrics["succeeded"] == 8
    assert queue.metrics["dead_letter"] == 4
    assert timeout.metrics["dead_letter"] == 3
    assert timeout.metrics["timeout_errors"] == 3


def test_phase9_stress_cli_reports_metrics(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "phase9-stress",
            "--config",
            str(ROOT / "configs" / "phase9_stress_gates.yaml"),
            "--workspace-root",
            str(tmp_path / "stress"),
        ],
    )

    assert result.exit_code == 0
    assert "PASS phase9_retriever_incremental_load" in result.output
    assert "first_indexed=32" in result.output
    assert "PASS phase9_queue_retry_budget" in result.output
    assert "dead_letter=4" in result.output
    assert "PASS phase9_worker_timeout_dead_letter" in result.output
    assert "timeout_errors=3" in result.output
