from collections.abc import Callable

from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.agent.loop import AgentLoop
from ai_local.queue.models import Job
from ai_local.queue.store import InMemoryQueueStore


def claim_one(store: InMemoryQueueStore) -> str | None:
    job = store.claim_next()
    return job.id if job else None


JobHandler = Callable[[Job], None]


class QueueWorker:
    def __init__(
        self,
        store: InMemoryQueueStore,
        handler: JobHandler,
        *,
        audit_store: InMemoryAuditStore | None = None,
    ) -> None:
        self._store = store
        self._handler = handler
        self._audit_store = audit_store

    def run_one(self) -> Job | None:
        job = self._store.claim_next()
        if job is None:
            return None
        self._store.mark_running(job)
        try:
            self._handler(job)
        except Exception as exc:  # noqa: BLE001
            self._store.mark_failed(job, str(exc))
        else:
            self._store.mark_succeeded(job)
        if self._audit_store is not None:
            self._audit_store.append(make_audit_event("job.run", job.id, job.status))
        return job


def make_agent_run_handler(loop: AgentLoop) -> JobHandler:
    def handle(job: Job) -> None:
        if job.type != "agent_run":
            msg = f"Unsupported job type: {job.type}"
            raise ValueError(msg)
        goal = job.payload.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            msg = "agent_run job needs goal"
            raise ValueError(msg)
        loop.run_once(job.id, goal)

    return handle
