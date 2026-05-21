from dataclasses import dataclass


@dataclass(frozen=True)
class WriteLockDecision:
    acquired: bool
    decision: str
    owner_run_id: str


class InMemoryThreadControl:
    def __init__(self) -> None:
        self._project_write_locks: dict[str, str] = {}

    def acquire_write(self, project_id: str, run_id: str) -> WriteLockDecision:
        owner = self._project_write_locks.get(project_id)
        if owner is None or owner == run_id:
            self._project_write_locks[project_id] = run_id
            return WriteLockDecision(True, "acquire_write_lock", run_id)
        return WriteLockDecision(False, "wait_for_write_lock", owner)

    def release_write(self, project_id: str, run_id: str) -> bool:
        if self._project_write_locks.get(project_id) != run_id:
            return False
        del self._project_write_locks[project_id]
        return True
