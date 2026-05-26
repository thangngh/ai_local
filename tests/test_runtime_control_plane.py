from pathlib import Path

from typer.testing import CliRunner

from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore, make_audit_event
from ai_local.cli import app
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.control_plane import (
    build_runtime_control_snapshot,
    render_runtime_control_snapshot,
)


def test_runtime_control_snapshot_reports_ok_state_with_schema_versions(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(id="job-ok", type="phase10", status=JobStatus.SUCCEEDED, payload={})
    )
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="run-ok", goal="Render runtime", status=AgentRunStatus.SUCCEEDED)
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.panel", "runtime", "ok"))

    snapshot = build_runtime_control_snapshot(tasks_db=tasks_db, audit_db=audit_db)
    rendered = render_runtime_control_snapshot(snapshot)

    assert snapshot.health == "ok"
    assert snapshot.queue_counts["succeeded"] == 1
    assert snapshot.agent_run_counts["succeeded"] == 1
    assert snapshot.schema_versions == {"agent_runs": 1, "audit": 1, "queue": 1}
    assert "RUNTIME_CONTROL health=ok" in rendered
    assert "ISSUES none" in rendered


def test_runtime_control_snapshot_surfaces_dead_letter_and_failed_runs(
    tmp_path: Path,
) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(
            id="job-dead",
            type="phase10",
            status=JobStatus.DEAD_LETTER,
            payload={},
            last_error="boom",
        )
    )
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="run-failed", goal="Broken", status=AgentRunStatus.FAILED)
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.panel", "runtime", "failed"))

    snapshot = build_runtime_control_snapshot(tasks_db=tasks_db, audit_db=audit_db)
    rendered = render_runtime_control_snapshot(snapshot)

    assert snapshot.health == "critical"
    assert "critical queue.dead_letter" in rendered
    assert "warn agent_runs.failed" in rendered


def test_runtime_control_panel_cli_renders_tui_ready_snapshot(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(Job(id="job-1", type="phase10", payload={}))
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="run-1", goal="Waiting", status=AgentRunStatus.WAITING_USER)
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.panel", "runtime", "wait"))

    result = CliRunner().invoke(
        app,
        [
            "runtime-control-panel",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
            "--recent-audit-limit",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "RUNTIME_CONTROL health=warn" in result.output
    assert "QUEUE " in result.output
    assert "pending=1" in result.output
    assert "AGENT_RUNS " in result.output
    assert "waiting_user=1" in result.output
    assert "RECENT_AUDIT" in result.output


def test_runtime_control_panel_cli_can_fail_on_critical(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(id="job-dead", type="phase10", status=JobStatus.DEAD_LETTER, payload={})
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.panel", "runtime", "critical"))

    result = CliRunner().invoke(
        app,
        [
            "runtime-control-panel",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
            "--fail-on-critical",
        ],
    )

    assert result.exit_code == 1
    assert "RUNTIME_CONTROL health=critical" in result.output
