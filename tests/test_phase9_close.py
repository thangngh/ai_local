from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.pipeline.phase9_close import run_phase9_close


ROOT = Path(__file__).resolve().parents[1]


def test_phase9_close_combines_replay_and_stress_gates(tmp_path: Path) -> None:
    result = run_phase9_close(
        replay_config=ROOT / "configs" / "phase9_replay_fixtures.yaml",
        stress_config=ROOT / "configs" / "phase9_stress_gates.yaml",
        workspace_root=tmp_path / "close",
        patch_levels_config=ROOT / "configs" / "patch_levels.yaml",
        audit_db=tmp_path / "audit.db",
    )

    assert result.passed is True
    assert result.replay_passed == 3
    assert result.replay_total == 3
    assert result.stress_passed == 3
    assert result.stress_total == 3
    assert result.reasons == []


def test_phase9_close_cli_reports_summary(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "phase9-close",
            "--replay-config",
            str(ROOT / "configs" / "phase9_replay_fixtures.yaml"),
            "--stress-config",
            str(ROOT / "configs" / "phase9_stress_gates.yaml"),
            "--workspace-root",
            str(tmp_path / "close"),
            "--patch-levels-config",
            str(ROOT / "configs" / "patch_levels.yaml"),
            "--audit-db",
            str(tmp_path / "audit.db"),
        ],
    )

    assert result.exit_code == 0
    assert "PASS phase9_close replay=3/3 stress=3/3" in result.output
