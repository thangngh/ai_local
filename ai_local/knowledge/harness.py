from ai_local.knowledge.models import KnowledgeItem
from ai_local.knowledge.policy import decide_knowledge


def accept_item(item: KnowledgeItem) -> bool:
    return decide_knowledge(item).decision == "use"
