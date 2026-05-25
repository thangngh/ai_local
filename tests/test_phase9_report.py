import json
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.pipeline.report import run_phase9_integration_report


ROOT = Path(__file__).resolve().parents[1]


def test_phase9_integration_report_ready_outputs_structured_decision(tmp_path: Path) -> None:
    report = run_phase9_integration_report(
        scenario="ready",
        workspace_root=tmp_path,
        patch_levels_config=ROOT / "configs" / "patch_levels.yaml",
    )

    assert report["status"] == "done"
    assert report["final_state"] == "DECISION_GATE"
    assert report["output_ready"] is True
    assert report["patch_decision"] == "accept"
    assert "SKILL_RUNTIME" in cast(list[str], report["stages"])
    assert "PATCH_PIPELINE" in cast(list[str], report["stages"])
    assert cast(int, report["audit_event_count"]) >= 2


def test_phase9_integration_report_cli_writes_json_file(tmp_path: Path) -> None:
    output = tmp_path / "phase9-report.json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "phase9-integration-report",
            "--scenario",
            "no-path",
            "--workspace-root",
            str(tmp_path),
            "--patch-levels-config",
            str(ROOT / "configs" / "patch_levels.yaml"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    stdout_payload = json.loads(result.output)
    assert payload == stdout_payload
    assert payload["status"] == "rollback"
    assert payload["final_state"] == "ROLLBACK"
    assert payload["hop_depth"] == 50
    assert payload["patch_decision"] == "rollback"


def test_phase9_integration_report_prompt_injection_stops_before_skill(tmp_path: Path) -> None:
    report = run_phase9_integration_report(
        scenario="prompt-injection",
        workspace_root=tmp_path,
        patch_levels_config=ROOT / "configs" / "patch_levels.yaml",
    )

    assert report["status"] == "quarantine"
    assert report["final_state"] == "QUARANTINE"
    assert report["skill_decision"] is None
    assert report["patch_decision"] is None
    assert "prompt_injection" in cast(list[str], report["risk_flags"])
