from collections.abc import Callable

from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.outbox.models import OutboxEvent, OutboxStatus
from ai_local.outbox.store import InMemoryOutboxStore


def can_dispatch(event: OutboxEvent, approved: bool) -> bool:
    return approved if event.requires_approval else True


SideEffectHandler = Callable[[OutboxEvent], dict[str, object]]


class OutboxDispatcher:
    def __init__(
        self,
        store: InMemoryOutboxStore,
        handler: SideEffectHandler,
        *,
        audit_store: InMemoryAuditStore | None = None,
    ) -> None:
        self._store = store
        self._handler = handler
        self._audit_store = audit_store

    def dispatch(self, event: OutboxEvent) -> OutboxEvent:
        if not can_dispatch(event, event.approved):
            event.status = OutboxStatus.HELD
            return self._record(event, "held")
        if self._store.already_dispatched(event.idempotency_key):
            event.status = OutboxStatus.DISPATCHED
            event.result = {"decision": "dispatch_once"}
            return self._record(event, "duplicate")
        event.attempts += 1
        event.result = self._handler(event)
        event.status = OutboxStatus.DISPATCHED
        return self._record(event, "dispatched")

    def dispatch_ready(self) -> list[OutboxEvent]:
        return [self.dispatch(event) for event in self._store.ready()]

    def _record(self, event: OutboxEvent, result: str) -> OutboxEvent:
        if self._audit_store is not None:
            self._audit_store.append(make_audit_event("outbox.dispatch", event.event_type, result))
        return event
