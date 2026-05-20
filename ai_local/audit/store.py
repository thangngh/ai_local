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

