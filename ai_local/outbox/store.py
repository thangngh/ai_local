from ai_local.outbox.models import OutboxEvent


class InMemoryOutboxStore:
    def __init__(self) -> None:
        self._events: list[OutboxEvent] = []

    def append(self, event: OutboxEvent) -> OutboxEvent:
        self._events.append(event)
        return event

    def ready(self) -> list[OutboxEvent]:
        return [event for event in self._events if event.status == "pending"]

    def already_dispatched(self, idempotency_key: str) -> bool:
        return any(
            event.idempotency_key == idempotency_key and event.status == "dispatched"
            for event in self._events
        )
