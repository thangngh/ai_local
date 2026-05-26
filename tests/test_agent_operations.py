from pathlib import Path

from typer.testing import CliRunner

from ai_local.agent.operations import cancel_agent_run, stop_agent_run
from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore
from ai_local.cli import app


def test_stop_agent_run_moves_running_to_stopped_and_audits(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(
            id="run-active",
            goal="Stop me",
            status=AgentRunStatus.RUNNING,
            decision="continue",
            next_state="PATCH",
        )
    )

    result = stop_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id="run-active")
    run = SQLiteAgentRunStore(tasks_db).get("run-active")
    audit = SQLiteAuditStore(audit_db).list_events()

    assert result.decision == "succeeded"
    assert run is not None
    assert run.status == AgentRunStatus.STOPPED
    assert run.decision == "stop"
    assert run.next_state == "STOP"
    assert audit[-1].action == "agent_run.stop"
    assert audit[-1].result == "succeeded"


def test_cancel_agent_run_moves_waiting_to_cancelled_and_audits(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="run-wait", goal="Cancel me", status=AgentRunStatus.WAITING_USER)
    )

    result = cancel_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id="run-wait")
    run = SQLiteAgentRunStore(tasks_db).get("run-wait")
    audit = SQLiteAuditStore(audit_db).list_events()

    assert result.decision == "succeeded"
    assert run is not None
    assert run.status == AgentRunStatus.CANCELLED
    assert run.decision == "cancel"
    assert run.next_state == "CANCELLED"
    assert audit[-1].action == "agent_run.cancel"
    assert audit[-1].result == "succeeded"


def test_agent_run_operations_deny_terminal_or_missing_runs(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="run-done", goal="Done", status=AgentRunStatus.SUCCEEDED)
    )

    cancel_done = cancel_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id="run-done")
    stop_missing = stop_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id="missing")
    run = SQLiteAgentRunStore(tasks_db).get("run-done")
    audit = SQLiteAuditStore(audit_db).list_events()

    assert cancel_done.decision == "denied"
    assert cancel_done.reason == "agent run cannot be cancelled from its current state"
    assert stop_missing.decision == "denied"
    assert stop_missing.reason == "agent run does not exist"
    assert run is not None
    assert run.status == AgentRunStatus.SUCCEEDED
    assert [event.result for event in audit] == ["denied", "denied"]


def test_agent_run_operation_cli_lists_stops_and_cancels(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    store = SQLiteAgentRunStore(tasks_db)
    store.create(AgentRun(id="run-stop", goal="Stop", status=AgentRunStatus.RUNNING))
    store.create(AgentRun(id="run-cancel", goal="Cancel", status=AgentRunStatus.PENDING))

    list_result = CliRunner().invoke(app, ["agent-runs", "--tasks-db", str(tasks_db)])
    stop_result = CliRunner().invoke(
        app,
        [
            "agent-run-stop",
            "run-stop",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
        ],
    )
    cancel_result = CliRunner().invoke(
        app,
        [
            "agent-run-cancel",
            "run-cancel",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
        ],
    )

    assert list_result.exit_code == 0
    assert "AGENT_RUN id=run-stop status=running" in list_result.output
    assert stop_result.exit_code == 0
    assert "PASS agent_run_stop id=run-stop status=stopped" in stop_result.output
    assert cancel_result.exit_code == 0
    assert "PASS agent_run_cancel id=run-cancel status=cancelled" in cancel_result.output
