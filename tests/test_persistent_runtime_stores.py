from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.agent.loop import AgentLoop
from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore, make_audit_event
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import SQLiteQueueStore
from ai_local.queue.worker import QueueWorker


def test_sqlite_audit_store_persists_events_across_instances(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    first = SQLiteAuditStore(db_path)
    first.append(make_audit_event("phase10.test", "target", "ok"))

    second = SQLiteAuditStore(db_path)
    events = second.list_events()

    assert len(events) == 1
    assert events[0].action == "phase10.test"
    assert events[0].target == "target"
    assert events[0].result == "ok"


def test_sqlite_agent_run_store_persists_agent_loop_state(tmp_path: Path) -> None:
    db_path = tmp_path / "tasks.db"
    store = SQLiteAgentRunStore(db_path)
    store.create(AgentRun(id="run-1", goal="Persist runtime store"))

    AgentLoop(store).run_once("run-1", "Persist runtime store")
    reloaded = SQLiteAgentRunStore(db_path).get("run-1")

    assert reloaded is not None
    assert reloaded.status == AgentRunStatus.PLANNED
    assert reloaded.decision == "continue"
    assert reloaded.next_state == "RETRIEVE"
    assert reloaded.plan[0].intent == "Analyze requirement: Persist runtime store"


def test_sqlite_queue_store_retries_and_dead_letters_across_workers(tmp_path: Path) -> None:
    db_path = tmp_path / "tasks.db"
    queue = SQLiteQueueStore(db_path)
    queue.enqueue(Job(id="job-1", type="phase10", payload={}, max_attempts=2))

    first = QueueWorker(
        SQLiteQueueStore(db_path),
        lambda _job: (_ for _ in ()).throw(RuntimeError("boom")),
    ).run_one()
    second = QueueWorker(
        SQLiteQueueStore(db_path),
        lambda _job: (_ for _ in ()).throw(RuntimeError("boom")),
    ).run_one()
    jobs = SQLiteQueueStore(db_path).list_jobs()

    assert first is not None
    assert first.status == JobStatus.PENDING
    assert first.attempts == 1
    assert second is not None
    assert second.status == JobStatus.DEAD_LETTER
    assert second.attempts == 2
    assert jobs[0].status == JobStatus.DEAD_LETTER
    assert jobs[0].last_error == "boom"


def test_runtime_store_stats_cli_reports_persistent_counts(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteAgentRunStore(tasks_db).create(AgentRun(id="run-1", goal="Stats"))
    SQLiteQueueStore(tasks_db).enqueue(Job(id="job-1", type="phase10", payload={}))
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.stats", "runtime", "ok"))

    result = CliRunner().invoke(
        app,
        [
            "runtime-store-stats",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
        ],
    )

    assert result.exit_code == 0
    assert "RUNTIME_AUDIT events=1" in result.output
    assert "RUNTIME_QUEUE pending=1" in result.output
    assert "RUNTIME_AGENT_RUNS pending=1" in result.output
