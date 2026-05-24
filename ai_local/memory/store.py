from ai_local.memory.models import (
    MemoryConflictRecord,
    MemoryEvidenceRecord,
    MemoryItem,
    MemoryUsageRecord,
)


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._items: list[MemoryItem] = []
        self._evidence: list[MemoryEvidenceRecord] = []
        self._conflicts: list[MemoryConflictRecord] = []
        self._usage: list[MemoryUsageRecord] = []

    def add(self, item: MemoryItem) -> None:
        self._items.append(item)

    def search(self, scope: str) -> list[MemoryItem]:
        return [item for item in self._items if item.scope == scope]

    def active(self, scope: str) -> list[MemoryItem]:
        return [item for item in self.search(scope) if item.status == "active"]

    def add_evidence(self, record: MemoryEvidenceRecord) -> None:
        self._evidence.append(record)

    def evidence_for(self, memory_id: str) -> tuple[MemoryEvidenceRecord, ...]:
        return tuple(record for record in self._evidence if record.memory_id == memory_id)

    def add_conflict(self, record: MemoryConflictRecord) -> None:
        self._conflicts.append(record)

    def open_conflicts_for(self, memory_id: str) -> tuple[MemoryConflictRecord, ...]:
        return tuple(
            record
            for record in self._conflicts
            if record.memory_id == memory_id and record.status == "open"
        )

    def add_usage(self, record: MemoryUsageRecord) -> None:
        self._usage.append(record)

    def usage_for(self, memory_id: str) -> tuple[MemoryUsageRecord, ...]:
        return tuple(record for record in self._usage if record.memory_id == memory_id)
