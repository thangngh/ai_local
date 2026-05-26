import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from ai_local.agent.state import AgentRun
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore, make_audit_event
from ai_local.cli import app
from ai_local.db.schema import migrate_component
from ai_local.queue.models import Job
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.backup import create_runtime_backup, restore_runtime_backup


def test_runtime_backup_creates_manifest_and_copies_databases(tmp_path: Path) -> None:
    tasks_db = tmp_path / "runtime" / "tasks.db"
    audit_db = tmp_path / "runtime" / "audit.db"
    backup_dir = tmp_path / "backup"
    SQLiteQueueStore(tasks_db).enqueue(Job(id="job-1", type="phase11", payload={}))
    SQLiteAgentRunStore(tasks_db).create(AgentRun(id="run-1", goal="backup"))
    SQLiteAuditStore(audit_db).append(make_audit_event("phase11.backup", "runtime", "ok"))

    result = create_runtime_backup(tasks_db=tasks_db, audit_db=audit_db, backup_dir=backup_dir)

    assert result.decision == "succeeded"
    assert (backup_dir / "tasks.db").is_file()
    assert (backup_dir / "audit.db").is_file()
    assert result.manifest_path == backup_dir / "manifest.json"
    assert '"queue": 1' in result.manifest_path.read_text(encoding="utf-8")


def test_runtime_restore_replaces_target_databases_after_schema_check(tmp_path: Path) -> None:
    source_tasks = tmp_path / "source" / "tasks.db"
    source_audit = tmp_path / "source" / "audit.db"
    target_tasks = tmp_path / "target" / "tasks.db"
    target_audit = tmp_path / "target" / "audit.db"
    backup_dir = tmp_path / "backup"
    SQLiteQueueStore(source_tasks).enqueue(Job(id="source-job", type="phase11", payload={}))
    SQLiteAgentRunStore(source_tasks).create(AgentRun(id="source-run", goal="restore"))
    SQLiteAuditStore(source_audit).append(make_audit_event("phase11.restore", "runtime", "ok"))
    SQLiteQueueStore(target_tasks).enqueue(Job(id="target-job", type="phase11", payload={}))
    create_runtime_backup(tasks_db=source_tasks, audit_db=source_audit, backup_dir=backup_dir)

    result = restore_runtime_backup(
        backup_dir=backup_dir,
        tasks_db=target_tasks,
        audit_db=target_audit,
    )

    assert result.decision == "succeeded"
    assert SQLiteQueueStore(target_tasks).get("source-job") is not None
    assert SQLiteQueueStore(target_tasks).get("target-job") is None
    assert SQLiteAgentRunStore(target_tasks).get("source-run") is not None
    assert SQLiteAuditStore(target_audit).count() == 1


def test_runtime_restore_denies_future_schema_backup(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    future_tasks = backup_dir / "tasks.db"
    future_audit = backup_dir / "audit.db"
    with sqlite3.connect(future_tasks) as connection:
        connection.row_factory = sqlite3.Row
        migrate_component(
            connection,
            component="queue",
            target_version=2,
            migrations={
                1: "CREATE TABLE IF NOT EXISTS queue_jobs(id TEXT);",
                2: "CREATE TABLE IF NOT EXISTS queue_jobs_v2(id TEXT);",
            },
        )
        migrate_component(
            connection,
            component="agent_runs",
            target_version=1,
            migrations={1: "CREATE TABLE IF NOT EXISTS agent_runs(id TEXT);"},
        )
    SQLiteAuditStore(future_audit).initialize()
    (backup_dir / "manifest.json").write_text(
        """
{
  "files": {
    "tasks_db": "tasks.db",
    "audit_db": "audit.db"
  }
}
""",
        encoding="utf-8",
    )

    result = restore_runtime_backup(
        backup_dir=backup_dir,
        tasks_db=tmp_path / "target" / "tasks.db",
        audit_db=tmp_path / "target" / "audit.db",
    )

    assert result.decision == "denied"
    assert result.reason == "queue schema is not at supported version 1"


def test_runtime_backup_and_restore_cli(tmp_path: Path) -> None:
    tasks_db = tmp_path / "runtime" / "tasks.db"
    audit_db = tmp_path / "runtime" / "audit.db"
    backup_dir = tmp_path / "backup"
    restored_tasks = tmp_path / "restored" / "tasks.db"
    restored_audit = tmp_path / "restored" / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(Job(id="job-cli", type="phase11", payload={}))
    SQLiteAuditStore(audit_db).append(make_audit_event("phase11.backup", "runtime", "ok"))

    backup = CliRunner().invoke(
        app,
        [
            "runtime-backup",
            str(backup_dir),
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
        ],
    )
    restore = CliRunner().invoke(
        app,
        [
            "runtime-restore",
            str(backup_dir),
            "--tasks-db",
            str(restored_tasks),
            "--audit-db",
            str(restored_audit),
        ],
    )

    assert backup.exit_code == 0
    assert "PASS runtime_backup" in backup.output
    assert restore.exit_code == 0
    assert "PASS runtime_restore" in restore.output
    assert SQLiteQueueStore(restored_tasks).get("job-cli") is not None
