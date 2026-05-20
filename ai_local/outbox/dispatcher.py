from ai_local.outbox.models import OutboxEvent


def can_dispatch(event: OutboxEvent, approved: bool) -> bool:
    return approved if event.requires_approval else True

