from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.pipeline.audit_chain import PipelineAuditChainStore
from ai_local.pipeline.replay import (
    load_phase9_replay_fixtures,
    run_phase9_replay_fixtures,
)


ROOT = Path(__file__).resolve().parents[1]


def test_phase9_replay_fixtures_cover_noise_conflict_and_no_path() -> None:
    fixtures = load_phase9_replay_fixtures(ROOT / "configs" / "phase9_replay_fixtures.yaml")

    assert len(fixtures) == 3
    assert {fixture.scenario for fixture in fixtures} == {
        "ready",
        "no-path",
        "prompt-injection",
    }
    assert max(fixture.expected_hop_depth for fixture in fixtures) == 50
    assert any(fixture.expected_noise_profile == "prompt_injection" for fixture in fixtures)
    assert any(fixture.expected_conflict_profile == "no_path" for fixture in fixtures)


def test_phase9_replay_passes_all_configured_fixtures(tmp_path: Path) -> None:
    audit_db = tmp_path / "audit.db"

    results = run_phase9_replay_fixtures(
        config_path=ROOT / "configs" / "phase9_replay_fixtures.yaml",
        workspace_root=tmp_path,
        patch_levels_config=ROOT / "configs" / "patch_levels.yaml",
        audit_db=audit_db,
    )

    assert [result.fixture_id for result in results] == [
        "phase9_ready_output",
        "phase9_no_path_rollback",
        "phase9_prompt_injection_quarantine",
    ]
    assert all(result.passed for result in results)
    assert all(result.chain_id for result in results)
    assert len(PipelineAuditChainStore(audit_db).list_summaries()) == 3


def test_phase9_replay_cli_reports_passes_and_persists_chains(tmp_path: Path) -> None:
    audit_db = tmp_path / "audit.db"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "phase9-replay",
            "--config",
            str(ROOT / "configs" / "phase9_replay_fixtures.yaml"),
            "--workspace-root",
            str(tmp_path),
            "--patch-levels-config",
            str(ROOT / "configs" / "patch_levels.yaml"),
            "--audit-db",
            str(audit_db),
        ],
    )

    assert result.exit_code == 0
    assert "PASS phase9_ready_output" in result.output
    assert "PASS phase9_no_path_rollback" in result.output
    assert "PASS phase9_prompt_injection_quarantine" in result.output
    assert len(PipelineAuditChainStore(audit_db).list_summaries()) == 3
