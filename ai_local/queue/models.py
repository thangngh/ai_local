from enum import StrEnum

from pydantic import BaseModel


class JobStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class Job(BaseModel):
    id: str
    type: str
    status: JobStatus = JobStatus.PENDING
    priority: int = 100
    payload: dict[str, object]

