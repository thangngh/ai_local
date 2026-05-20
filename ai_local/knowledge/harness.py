from ai_local.knowledge.models import KnowledgeItem


def accept_item(item: KnowledgeItem) -> bool:
    return item.rank >= 60 and item.confidence >= 0.60

