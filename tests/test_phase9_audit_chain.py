import json
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.pipeline.audit_chain import PipelineAuditChainStore
from ai_local.pipeline.report import run_phase9_integration_report


ROOT = Path(__file__).resolve().parents[1]


def test_phase9_report_persists_evidence_and_audit_chain(tmp_path: Path) -> None:
    audit_db = tmp_path / "audit.db"

    report = run_phase9_integration_report(
        scenario="ready",
        workspace_root=tmp_path,
        patch_levels_config=ROOT / "configs" / "patch_levels.yaml",
        audit_db=audit_db,
    )

    assert isinstance(report["chain_id"], str)
    store = PipelineAuditChainStore(audit_db)
    summaries = store.list_summaries()
    persisted = store.read_report(str(report["chain_id"]))

    assert len(summaries) == 1
    assert summaries[0].status == "done"
    assert summaries[0].final_state == "DECISION_GATE"
    assert summaries[0].evidence_count == len(cast(list[str], report["evidence_refs"]))
    assert summaries[0].audit_event_count == report["audit_event_count"]
    assert persisted is not None
    assert persisted["chain_id"] == report["chain_id"]
    assert persisted["patch_decision"] == "accept"


def test_phase9_report_cli_persists_chain_and_lists_summary(tmp_path: Path) -> None:
    audit_db = tmp_path / "audit.db"
    output = tmp_path / "no-path.json"
    runner = CliRunner()

    report_result = runner.invoke(
        app,
        [
            "phase9-integration-report",
            "--scenario",
            "no-path",
            "--workspace-root",
            str(tmp_path),
            "--patch-levels-config",
            str(ROOT / "configs" / "patch_levels.yaml"),
            "--audit-db",
            str(audit_db),
            "--output",
            str(output),
        ],
    )
    chains_result = runner.invoke(
        app,
        [
            "phase9-audit-chains",
            "--audit-db",
            str(audit_db),
        ],
    )

    assert report_result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "rollback"
    assert payload["chain_id"]
    assert chains_result.exit_code == 0
    assert str(payload["chain_id"]) in chains_result.output
    assert "scenario=no-path" in chains_result.output
    assert "final_state=ROLLBACK" in chains_result.output
