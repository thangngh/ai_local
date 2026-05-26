from pathlib import Path

from typer.testing import CliRunner

from ai_local.audit.store import SQLiteAuditStore
from ai_local.cli import app
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.operations import cancel_queue_job, retry_dead_letter_job
from ai_local.queue.store import SQLiteQueueStore


def test_retry_dead_letter_job_resets_attempts_and_audits(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(
            id="job-dead",
            type="phase11",
            status=JobStatus.DEAD_LETTER,
            payload={},
            attempts=3,
            last_error="boom",
        )
    )

    result = retry_dead_letter_job(tasks_db=tasks_db, audit_db=audit_db, job_id="job-dead")
    job = SQLiteQueueStore(tasks_db).get("job-dead")
    audit = SQLiteAuditStore(audit_db).list_events()

    assert result.decision == "succeeded"
    assert job is not None
    assert job.status == JobStatus.PENDING
    assert job.attempts == 0
    assert job.last_error is None
    assert audit[-1].action == "queue.retry"
    assert audit[-1].result == "succeeded"


def test_retry_denies_non_dead_letter_and_audits(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(Job(id="job-pending", type="phase11", payload={}))

    result = retry_dead_letter_job(tasks_db=tasks_db, audit_db=audit_db, job_id="job-pending")
    job = SQLiteQueueStore(tasks_db).get("job-pending")
    audit = SQLiteAuditStore(audit_db).list_events()

    assert result.decision == "denied"
    assert result.reason == "only dead-letter jobs can be retried"
    assert job is not None
    assert job.status == JobStatus.PENDING
    assert audit[-1].action == "queue.retry"
    assert audit[-1].result == "denied"


def test_cancel_pending_or_claimed_job_and_denies_running(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    store = SQLiteQueueStore(tasks_db)
    store.enqueue(Job(id="job-pending", type="phase11", payload={}))
    store.enqueue(Job(id="job-running", type="phase11", status=JobStatus.RUNNING, payload={}))

    cancelled = cancel_queue_job(tasks_db=tasks_db, audit_db=audit_db, job_id="job-pending")
    denied = cancel_queue_job(tasks_db=tasks_db, audit_db=audit_db, job_id="job-running")
    pending_job = store.get("job-pending")
    running_job = store.get("job-running")
    audit = SQLiteAuditStore(audit_db).list_events()

    assert cancelled.decision == "succeeded"
    assert pending_job is not None
    assert pending_job.status == JobStatus.CANCELLED
    assert pending_job.last_error == "cancelled by operator"
    assert denied.decision == "denied"
    assert denied.reason == "only pending or claimed jobs can be cancelled safely"
    assert running_job is not None
    assert running_job.status == JobStatus.RUNNING
    assert [event.result for event in audit] == ["succeeded", "denied"]


def test_queue_operation_cli_lists_retries_and_cancels(tmp_path: Path) -> None:
    tasks_db = tmp_path / "tasks.db"
    audit_db = tmp_path / "audit.db"
    store = SQLiteQueueStore(tasks_db)
    store.enqueue(
        Job(
            id="job-dead",
            type="phase11",
            status=JobStatus.DEAD_LETTER,
            payload={},
            attempts=2,
            last_error="boom",
        )
    )
    store.enqueue(Job(id="job-cancel", type="phase11", payload={}))

    list_result = CliRunner().invoke(app, ["queue-jobs", "--tasks-db", str(tasks_db)])
    retry_result = CliRunner().invoke(
        app,
        [
            "queue-retry",
            "job-dead",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
        ],
    )
    cancel_result = CliRunner().invoke(
        app,
        [
            "queue-cancel",
            "job-cancel",
            "--tasks-db",
            str(tasks_db),
            "--audit-db",
            str(audit_db),
        ],
    )

    assert list_result.exit_code == 0
    assert "QUEUE_JOB id=job-dead" in list_result.output
    assert retry_result.exit_code == 0
    assert "PASS queue_retry id=job-dead status=pending" in retry_result.output
    assert cancel_result.exit_code == 0
    assert "PASS queue_cancel id=job-cancel status=cancelled" in cancel_result.output
