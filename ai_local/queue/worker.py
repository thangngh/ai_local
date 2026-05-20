from ai_local.queue.store import InMemoryQueueStore


def claim_one(store: InMemoryQueueStore) -> str | None:
    job = store.claim_next()
    return job.id if job else None

