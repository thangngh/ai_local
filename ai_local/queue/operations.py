from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ai_local.audit.store import SQLiteAuditStore, make_audit_event
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import SQLiteQueueStore


QueueOperationDecision = Literal["succeeded", "denied"]


@dataclass(frozen=True)
class QueueOperationResult:
    decision: QueueOperationDecision
    reason: str
    job: Job | None = None
    audit_action: str | None = None


def list_queue_jobs(*, tasks_db: Path) -> list[Job]:
    return SQLiteQueueStore(tasks_db).list_jobs()


def retry_dead_letter_job(
    *,
    tasks_db: Path,
    audit_db: Path,
    job_id: str,
) -> QueueOperationResult:
    queue = SQLiteQueueStore(tasks_db)
    audit = SQLiteAuditStore(audit_db)
    schema_error = _schema_error(queue)
    if schema_error is not None:
        return _audit_denial(audit, "queue.retry", job_id, schema_error)

    job = queue.get(job_id)
    if job is None:
        return _audit_denial(audit, "queue.retry", job_id, "queue job does not exist")
    if job.status != JobStatus.DEAD_LETTER:
        return _audit_denial(audit, "queue.retry", job_id, "only dead-letter jobs can be retried")

    retried = queue.replace(
        job.model_copy(
            update={
                "status": JobStatus.PENDING,
                "attempts": 0,
                "last_error": None,
            }
        )
    )
    audit.append(make_audit_event("queue.retry", job_id, "succeeded"))
    return QueueOperationResult(
        decision="succeeded",
        reason="dead-letter job moved back to pending",
        job=retried,
        audit_action="queue.retry",
    )


def cancel_queue_job(
    *,
    tasks_db: Path,
    audit_db: Path,
    job_id: str,
) -> QueueOperationResult:
    queue = SQLiteQueueStore(tasks_db)
    audit = SQLiteAuditStore(audit_db)
    schema_error = _schema_error(queue)
    if schema_error is not None:
        return _audit_denial(audit, "queue.cancel", job_id, schema_error)

    job = queue.get(job_id)
    if job is None:
        return _audit_denial(audit, "queue.cancel", job_id, "queue job does not exist")
    if job.status not in {JobStatus.PENDING, JobStatus.CLAIMED}:
        return _audit_denial(
            audit,
            "queue.cancel",
            job_id,
            "only pending or claimed jobs can be cancelled safely",
        )

    cancelled = queue.replace(
        job.model_copy(
            update={
                "status": JobStatus.CANCELLED,
                "last_error": "cancelled by operator",
            }
        )
    )
    audit.append(make_audit_event("queue.cancel", job_id, "succeeded"))
    return QueueOperationResult(
        decision="succeeded",
        reason="queue job cancelled",
        job=cancelled,
        audit_action="queue.cancel",
    )


def _schema_error(queue: SQLiteQueueStore) -> str | None:
    versions = queue.schema_versions()
    if versions.get("queue") != SQLiteQueueStore.TARGET_VERSION:
        return "queue schema is not at supported version"
    return None


def _audit_denial(
    audit: SQLiteAuditStore,
    action: str,
    job_id: str,
    reason: str,
) -> QueueOperationResult:
    audit.append(make_audit_event(action, job_id, "denied"))
    return QueueOperationResult(
        decision="denied",
        reason=reason,
        audit_action=action,
    )
