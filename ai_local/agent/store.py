from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.planner.models import PlanItem


class InMemoryAgentRunStore:
    def __init__(self) -> None:
        self._runs: dict[str, AgentRun] = {}

    def create(self, run: AgentRun) -> AgentRun:
        self._runs[run.id] = run
        return run

    def get(self, run_id: str) -> AgentRun | None:
        return self._runs.get(run_id)

    def mark_planned(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        run = self._runs[run_id]
        run.plan = list(plan)
        run.status = AgentRunStatus.PLANNED
        run.decision = "continue"
        run.next_state = "RETRIEVE"
        return run

    def mark_waiting_user(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        run = self._runs[run_id]
        run.plan = list(plan)
        run.status = AgentRunStatus.WAITING_USER
        run.decision = "ask_user"
        run.next_state = "ASK_USER"
        return run

    def mark_stopped(self, run_id: str, plan: list[PlanItem]) -> AgentRun:
        run = self._runs[run_id]
        run.plan = list(plan)
        run.status = AgentRunStatus.STOPPED
        run.decision = "stop"
        run.next_state = "STOP"
        return run

    def mark_running(self, run_id: str, *, decision: str, next_state: str) -> AgentRun:
        run = self._runs[run_id]
        run.status = AgentRunStatus.RUNNING
        run.decision = decision
        run.next_state = next_state
        return run

    def mark_succeeded(self, run_id: str) -> AgentRun:
        run = self._runs[run_id]
        run.status = AgentRunStatus.SUCCEEDED
        run.decision = "finish"
        run.next_state = "DONE"
        return run
