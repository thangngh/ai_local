from pydantic import BaseModel


class OutboxEvent(BaseModel):
    event_type: str
    idempotency_key: str
    payload: dict[str, object]
    requires_approval: bool = False

