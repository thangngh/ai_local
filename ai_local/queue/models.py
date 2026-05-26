from enum import StrEnum

from pydantic import BaseModel


class JobStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class Job(BaseModel):
    id: str
    type: str
    status: JobStatus = JobStatus.PENDING
    priority: int = 100
    payload: dict[str, object]
    attempts: int = 0
    max_attempts: int = 3
    last_error: str | None = None
