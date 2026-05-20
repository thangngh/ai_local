from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import InMemoryQueueStore


def test_queue_claims_highest_priority_pending_job_once() -> None:
    store = InMemoryQueueStore()
    store.enqueue(Job(id="slow", type="agent_run", priority=100, payload={}))
    store.enqueue(Job(id="fast", type="agent_run", priority=1, payload={}))

    first = store.claim_next()
    second = store.claim_next()

    assert first is not None
    assert first.id == "fast"
    assert first.status == JobStatus.CLAIMED
    assert second is not None
    assert second.id == "slow"

