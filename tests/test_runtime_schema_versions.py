import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore, make_audit_event
from ai_local.cli import app
from ai_local.db.schema import migrate_component, schema_version
from ai_local.queue.models import Job
from ai_local.queue.store import SQLiteQueueStore


def test_runtime_stores_record_schema_versions_idempotently(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"

    SQLiteQueueStore(tasks_db).enqueue(Job(id="job-1", type="phase10", payload={}))
    SQLiteAgentRunStore(tasks_db).initialize()
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.schema", "audit", "ok"))
    SQLiteQueueStore(tasks_db).initialize()
    SQLiteAgentRunStore(tasks_db).initialize()
    SQLiteAuditStore(audit_db).initialize()

    queue_versions = SQLiteQueueStore(tasks_db).schema_versions()
    run_versions = SQLiteAgentRunStore(tasks_db).schema_versions()
    audit_versions = SQLiteAuditStore(audit_db).schema_versions()

    assert queue_versions["queue"] == 1
    assert run_versions["agent_runs"] == 1
    assert audit_versions["audit"] == 1
    assert SQLiteQueueStore(tasks_db).list_jobs()[0].id == "job-1"
    assert SQLiteAuditStore(audit_db).count() == 1


def test_runtime_schema_migration_rejects_newer_unknown_version(tmp_path: Path) -> None:
    db_path = tmp_path / "future.db"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        migrate_component(
            connection,
            component="queue",
            target_version=2,
            migrations={
                1: "CREATE TABLE IF NOT EXISTS sample(id TEXT);",
                2: "CREATE TABLE IF NOT EXISTS sample_v2(id TEXT);",
            },
        )
        assert schema_version(connection, "queue") == 2

    with pytest.raises(ValueError, match="newer than supported"):
        SQLiteQueueStore(db_path).initialize()


def test_runtime_schema_versions_cli_reports_components(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).initialize()
    SQLiteAgentRunStore(tasks_db).initialize()
    SQLiteAuditStore(audit_db).initialize()

    result = CliRunner().invoke(
        app,
        [
            "runtime-schema-versions",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
        ],
    )

    assert result.exit_code == 0
    assert "SCHEMA_VERSION component=agent_runs version=1" in result.output
    assert "SCHEMA_VERSION component=audit version=1" in result.output
    assert "SCHEMA_VERSION component=queue version=1" in result.output
