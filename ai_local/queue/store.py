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

