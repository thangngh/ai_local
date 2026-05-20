from ai_local.memory.models import MemoryItem


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: list[MemoryItem] = []

    def add(self, item: MemoryItem) -> None:
        self._items.append(item)

    def search(self, scope: str) -> list[MemoryItem]:
        return [item for item in self._items if item.scope == scope]

