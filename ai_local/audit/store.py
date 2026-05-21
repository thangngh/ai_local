from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class AuditEvent:
    action: str
    target: str
    result: str
    created_at: str


def make_audit_event(action: str, target: str, result: str) -> AuditEvent:
    return AuditEvent(
        action=action,
        target=target,
        result=result,
        created_at=datetime.now(UTC).isoformat(),
    )


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def list_events(self) -> list[AuditEvent]:
        return list(self._events)
