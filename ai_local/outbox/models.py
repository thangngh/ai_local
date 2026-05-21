from enum import StrEnum

from pydantic import BaseModel, Field


class OutboxStatus(StrEnum):
    PENDING = "pending"
    HELD = "held"
    DISPATCHED = "dispatched"


class OutboxEvent(BaseModel):
    id: str
    event_type: str
    idempotency_key: str
    payload: dict[str, object]
    requires_approval: bool = False
    approved: bool = False
    status: OutboxStatus = OutboxStatus.PENDING
    attempts: int = 0
    result: dict[str, object] = Field(default_factory=dict)
