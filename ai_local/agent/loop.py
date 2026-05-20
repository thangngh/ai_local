from dataclasses import dataclass


@dataclass(frozen=True)
class AgentLoopResult:
    status: str
    message: str


class AgentLoop:
    def run_once(self, task_id: str) -> AgentLoopResult:
        return AgentLoopResult(status="not_implemented", message=f"Task {task_id} is queued")

