from collections.abc import Iterable

from ai_local.knowledge.models import KnowledgeItem


class InMemoryKnowledgeStore:
    def __init__(self) -> None:
        self._items: list[KnowledgeItem] = []

    def add(self, item: KnowledgeItem) -> None:
        self._items.append(item)

    def all(self) -> Iterable[KnowledgeItem]:
        return tuple(self._items)

    def find_by_claim(self, claim: str) -> tuple[KnowledgeItem, ...]:
        normalized = _normalize_claim(claim)
        return tuple(item for item in self._items if _normalize_claim(item.claim) == normalized)

    def find_conflicts(self, item: KnowledgeItem) -> tuple[KnowledgeItem, ...]:
        normalized = _normalize_claim(item.claim)
        return tuple(
            stored
            for stored in self._items
            if _normalize_claim(stored.claim) == normalized
            and stored.source_ref != item.source_ref
            and stored.conflict_score >= 0.70
        )


def _normalize_claim(claim: str) -> str:
    return " ".join(claim.casefold().split())

