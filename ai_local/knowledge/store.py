from collections.abc import Iterable

from ai_local.knowledge.models import KnowledgeItem


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self._items: list[KnowledgeItem] = []

    def add(self, item: KnowledgeItem) -> None:
        self._items.append(item)

    def all(self) -> Iterable[KnowledgeItem]:
        return tuple(self._items)

