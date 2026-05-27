import json
from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.harness.phase_fast_gate import (
    load_phase_fast_gate_cases,
    phase_fast_gate_report,
    run_phase_fast_gates,
    write_phase_fast_gate_report,
)


ROOT = Path(__file__).resolve().parents[2]


def test_phase_fast_gate_config_covers_phase_1_to_phase_10() -> None:
    source_ref, cases = load_phase_fast_gate_cases(ROOT / "configs" / "phase_fast_gates.yaml")
    phases = {case.phase for case in cases}

    assert source_ref == "phase_1_to_phase_11_current"
    assert "phase_1_core_loop" in phases
    assert "phase_9_integrated_pipeline" in phases
    assert "phase_10_production_hardening" in phases
    assert "phase_11_operator_tui" in phases
    assert len(cases) >= 22


def test_phase_fast_gate_runs_phase10_smoke_subset(tmp_path: Path) -> None:
    config = tmp_path / "phase_fast_gates.yaml"
    config.write_text(
        """
phase_fast_gates:
  source_ref: test_subset
  gates:
    - id: store
      phase: phase_10_production_hardening
      runner: runtime_store_smoke
    - id: schema
      phase: phase_10_production_hardening
      runner: runtime_schema_smoke
    - id: sandbox
      phase: phase_10_production_hardening
      runner: tool_sandbox_smoke
    - id: control
      phase: phase_10_production_hardening
      runner: runtime_control_smoke
""",
        encoding="utf-8",
    )

    summary = run_phase_fast_gates(
        config_path=config,
        root=ROOT,
        workspace_root=tmp_path / "workspace",
    )

    assert summary.passed
    assert summary.passed_count == 4
    assert summary.total == 4
    assert summary.generated_at
    assert str(tmp_path / "workspace") == summary.workspace_root


def test_phase_fast_gate_cli_reports_subset(tmp_path: Path) -> None:
    config = tmp_path / "phase_fast_gates.yaml"
    config.write_text(
        """
phase_fast_gates:
  source_ref: cli_subset
  gates:
    - id: control
      phase: phase_10_production_hardening
      runner: runtime_control_smoke
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "phase-fast-gate",
            "--config",
            str(config),
            "--root",
            str(ROOT),
            "--workspace-root",
            str(tmp_path / "workspace"),
            "--output",
            str(tmp_path / "report.json"),
        ],
    )

    assert result.exit_code == 0
    assert "PASS phase_fast_gate source=cli_subset passed=1/1" in result.output
    assert f"REPORT {tmp_path / 'report.json'}" in result.output
    assert "phase_10_production_hardening.control" in result.output
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["source_ref"] == "cli_subset"
    assert payload["results"][0]["runner"] == "runtime_control_smoke"


def test_phase_fast_gate_unknown_runner_fails(tmp_path: Path) -> None:
    config = tmp_path / "phase_fast_gates.yaml"
    config.write_text(
        """
phase_fast_gates:
  source_ref: bad_subset
  gates:
    - id: bad
      phase: phase_10_production_hardening
      runner: missing_runner
""",
        encoding="utf-8",
    )

    summary = run_phase_fast_gates(
        config_path=config,
        root=ROOT,
        workspace_root=tmp_path / "workspace",
    )

    assert not summary.passed
    assert summary.results[0].summary == "unknown fast gate runner"


def test_phase_fast_gate_clean_workspace_is_idempotent(tmp_path: Path) -> None:
    config = tmp_path / "phase_fast_gates.yaml"
    workspace = tmp_path / "workspace"
    config.write_text(
        """
phase_fast_gates:
  source_ref: clean_subset
  gates:
    - id: store
      phase: phase_10_production_hardening
      runner: runtime_store_smoke
    - id: queue_ops
      phase: phase_11_operator_tui
      runner: queue_operations_smoke
""",
        encoding="utf-8",
    )
    first = run_phase_fast_gates(
        config_path=config,
        root=ROOT,
        workspace_root=workspace,
        clean=True,
    )
    second = run_phase_fast_gates(
        config_path=config,
        root=ROOT,
        workspace_root=workspace,
        clean=True,
    )
    assert first.passed
    assert second.passed


def test_phase_fast_gate_report_writer_persists_json_artifact(tmp_path: Path) -> None:
    config = tmp_path / "phase_fast_gates.yaml"
    output = tmp_path / "reports" / "phase-fast.json"
    config.write_text(
        """
phase_fast_gates:
  source_ref: writer_subset
  gates:
    - id: sandbox
      phase: phase_10_production_hardening
      runner: tool_sandbox_smoke
""",
        encoding="utf-8",
    )
    summary = run_phase_fast_gates(
        config_path=config,
        root=ROOT,
        workspace_root=tmp_path / "workspace",
    )

    write_phase_fast_gate_report(summary, output)
    payload = phase_fast_gate_report(summary)
    loaded = json.loads(output.read_text(encoding="utf-8"))

    assert loaded == payload
    assert loaded["passed_count"] == 1
    assert loaded["results"][0]["summary"] == "sandbox_decision=succeeded"
