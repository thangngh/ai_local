from dataclasses import dataclass

from ai_local.agent.store import InMemoryAgentRunStore
from ai_local.planner.gate import PlanGateDecision, decide_plan
from ai_local.planner.models import PlanGateSignals
from ai_local.planner.models import PlanItem
from ai_local.planner.service import plan_from_goal


@dataclass(frozen=True)
class AgentLoopResult:
    status: str
    message: str
    plan: list[PlanItem]
    decision: PlanGateDecision


class AgentLoop:
    def __init__(self, run_store: InMemoryAgentRunStore | None = None) -> None:
        self._run_store = run_store

    def run_once(
        self,
        task_id: str,
        goal: str,
        signals: PlanGateSignals | None = None,
    ) -> AgentLoopResult:
        plan = plan_from_goal(goal)
        decision = decide_plan(plan, signals)
        if self._run_store is not None:
            self._record_plan_decision(task_id, plan, decision)
        return AgentLoopResult(
            status=self._status_for_decision(decision),
            message=f"Task {task_id} plan gate decided {decision.decision}",
            plan=plan,
            decision=decision,
        )

    def _record_plan_decision(
        self,
        task_id: str,
        plan: list[PlanItem],
        decision: PlanGateDecision,
    ) -> None:
        store = self._run_store
        if store is None:
            return
        if decision.decision == "ask_user":
            store.mark_waiting_user(task_id, plan)
            return
        if decision.decision == "stop":
            store.mark_stopped(task_id, plan)
            return
        store.mark_planned(task_id, plan)

    @staticmethod
    def _status_for_decision(decision: PlanGateDecision) -> str:
        status_by_decision = {
            "continue": "planned",
            "ask_user": "waiting_user",
            "stop": "stopped",
        }
        return status_by_decision[decision.decision]
