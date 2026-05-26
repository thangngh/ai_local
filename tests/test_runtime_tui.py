from pathlib import Path

from typer.testing import CliRunner

from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore, make_audit_event
from ai_local.cli import app
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.control_plane import build_runtime_control_snapshot
from ai_local.runtime.tui import render_runtime_tui_frame, run_runtime_tui_frames


def test_runtime_tui_frame_renders_operator_sections(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(id="job-ok", type="phase11", status=JobStatus.SUCCEEDED, payload={})
    )
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="run-ok", goal="TUI", status=AgentRunStatus.SUCCEEDED)
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase11.tui", "runtime", "ok"))

    snapshot = build_runtime_control_snapshot(tasks_db=tasks_db, audit_db=audit_db)
    rendered = render_runtime_tui_frame(snapshot)

    assert "AI LOCAL RUNTIME" in rendered
    assert "FRAME iteration=1 health=ok" in rendered
    assert "[queue]" in rendered
    assert "succeeded=1" in rendered
    assert "[agent-runs]" in rendered
    assert "[schema]" in rendered
    assert "audit=v1" in rendered
    assert "[issues]\n- none" in rendered


def test_runtime_tui_frames_refreshes_deterministically(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(Job(id="job-1", type="phase11", payload={}))

    frames = run_runtime_tui_frames(
        tasks_db=tasks_db,
        audit_db=audit_db,
        iterations=2,
        refresh_seconds=0,
    )

    assert [frame.iteration for frame in frames] == [1, 2]
    assert all(frame.health == "ok" for frame in frames)
    assert "pending=1" in frames[0].text


def test_runtime_tui_cli_outputs_frame_and_can_fail_on_critical(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(id="job-dead", type="phase11", status=JobStatus.DEAD_LETTER, payload={})
    )

    result = CliRunner().invoke(
        app,
        [
            "runtime-tui",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
            "--fail-on-critical",
        ],
    )

    assert result.exit_code == 1
    assert "AI LOCAL RUNTIME" in result.output
    assert "health=critical" in result.output
    assert "queue.dead_letter" in result.output
