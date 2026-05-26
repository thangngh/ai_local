import json
import sqlite3
from pathlib import Path

from ai_local.db.schema import list_schema_versions, migrate_component
from ai_local.queue.models import Job, JobStatus


class InMemoryQueueStore:
    def __init__(self) -> None:
        self._jobs: list[Job] = []

    def enqueue(self, job: Job) -> None:
        self._jobs.append(job)

    def claim_next(self) -> Job | None:
        pending = [job for job in self._jobs if job.status == JobStatus.PENDING]
        if not pending:
            return None
        job = sorted(pending, key=lambda item: item.priority)[0]
        job.status = JobStatus.CLAIMED
        return job

    def mark_running(self, job: Job) -> Job:
        job.status = JobStatus.RUNNING
        job.attempts += 1
        return job

    def mark_succeeded(self, job: Job) -> Job:
        job.status = JobStatus.SUCCEEDED
        return job

    def mark_failed(self, job: Job, error: str) -> Job:
        job.last_error = error
        job.status = JobStatus.DEAD_LETTER if job.attempts >= job.max_attempts else JobStatus.PENDING
        return job


class SQLiteQueueStore:
    COMPONENT = "queue"
    TARGET_VERSION = 1

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            migrate_component(
                connection,
                component=self.COMPONENT,
                target_version=self.TARGET_VERSION,
                migrations={
                    1: """
                    CREATE TABLE IF NOT EXISTS queue_jobs (
                        id TEXT PRIMARY KEY,
                        type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        attempts INTEGER NOT NULL,
                        max_attempts INTEGER NOT NULL,
                        last_error TEXT
                    );
                    """,
                },
            )

    def enqueue(self, job: Job) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO queue_jobs(
                    id, type, status, priority, payload_json, attempts, max_attempts, last_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _job_params(job),
            )

    def claim_next(self) -> Job | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM queue_jobs
                WHERE status = ?
                ORDER BY priority ASC, id ASC
                LIMIT 1
                """,
                (JobStatus.PENDING.value,),
            ).fetchone()
            if row is None:
                return None
            job = _job_from_row(row).model_copy(update={"status": JobStatus.CLAIMED})
            self._upsert(connection, job)
            return job

    def mark_running(self, job: Job) -> Job:
        running = job.model_copy(
            update={"status": JobStatus.RUNNING, "attempts": job.attempts + 1}
        )
        self._persist(running)
        return running

    def mark_succeeded(self, job: Job) -> Job:
        succeeded = job.model_copy(update={"status": JobStatus.SUCCEEDED})
        self._persist(succeeded)
        return succeeded

    def mark_failed(self, job: Job, error: str) -> Job:
        failed_status = JobStatus.DEAD_LETTER if job.attempts >= job.max_attempts else JobStatus.PENDING
        failed = job.model_copy(update={"status": failed_status, "last_error": error})
        self._persist(failed)
        return failed

    def list_jobs(self) -> list[Job]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM queue_jobs ORDER BY priority ASC, id ASC").fetchall()
        return [_job_from_row(row) for row in rows]

    def get(self, job_id: str) -> Job | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM queue_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return _job_from_row(row)

    def replace(self, job: Job) -> Job:
        self._persist(job)
        return job

    def status_counts(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM queue_jobs
                GROUP BY status
                ORDER BY status
                """
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def schema_versions(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as connection:
            versions = list_schema_versions(connection)
        return {item.component: item.version for item in versions}

    def _persist(self, job: Job) -> None:
        self.initialize()
        with self._connect() as connection:
            self._upsert(connection, job)

    def _upsert(self, connection: sqlite3.Connection, job: Job) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO queue_jobs(
                id, type, status, priority, payload_json, attempts, max_attempts, last_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _job_params(job),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _job_params(job: Job) -> tuple[str, str, str, int, str, int, int, str | None]:
    return (
        job.id,
        job.type,
        job.status.value,
        job.priority,
        json.dumps(job.payload, sort_keys=True),
        job.attempts,
        job.max_attempts,
        job.last_error,
    )


def _job_from_row(row: sqlite3.Row) -> Job:
    payload = json.loads(str(row["payload_json"]))
    return Job(
        id=str(row["id"]),
        type=str(row["type"]),
        status=JobStatus(str(row["status"])),
        priority=int(row["priority"]),
        payload=payload if isinstance(payload, dict) else {},
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        last_error=str(row["last_error"]) if row["last_error"] is not None else None,
    )
