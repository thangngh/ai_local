from dataclasses import dataclass
from typing import Protocol

from ai_local.agent.store import InMemoryAgentRunStore
from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.confirmation.models import ConfirmationResolution
from ai_local.evaluator.models import (
    EvaluationEvidence,
    EvaluationResult,
    EvaluationRoute,
    ObservationEvaluationInput,
)
from ai_local.evaluator.service import (
    evaluate_observation,
    re_evaluate_after_confirmation,
    re_evaluate_with_context,
    route_evaluation,
)
from ai_local.planner.gate import PlanGateDecision, decide_plan
from ai_local.planner.models import PlanGateSignals
from ai_local.planner.models import PlanItem
from ai_local.planner.service import plan_from_goal
from ai_local.retrieval.models import ContextPackage


class ContextRetriever(Protocol):
    def retrieve(self, query: str) -> ContextPackage: ...


@dataclass(frozen=True)
class AgentLoopResult:
    status: str
    message: str
    plan: list[PlanItem]
    decision: PlanGateDecision
    context: ContextPackage | None = None


@dataclass(frozen=True)
class AgentEvaluationResult:
    evaluation: EvaluationResult
    route: EvaluationRoute
    context: ContextPackage | None = None


class AgentLoop:
    def __init__(
        self,
        run_store: InMemoryAgentRunStore | None = None,
        context_retriever: ContextRetriever | None = None,
        audit_store: InMemoryAuditStore | None = None,
    ) -> None:
        self._run_store = run_store
        self._context_retriever = context_retriever
        self._audit_store = audit_store

    def run_once(
        self,
        task_id: str,
        goal: str,
        signals: PlanGateSignals | None = None,
    ) -> AgentLoopResult:
        plan = plan_from_goal(goal)
        decision = decide_plan(plan, signals)
        context = self._retrieve_context(goal, decision)
        if self._run_store is not None:
            self._record_plan_decision(task_id, plan, decision)
        return AgentLoopResult(
            status=self._status_for_decision(decision),
            message=f"Task {task_id} plan gate decided {decision.decision}",
            plan=plan,
            decision=decision,
            context=context,
        )

    def _retrieve_context(
        self,
        goal: str,
        decision: PlanGateDecision,
    ) -> ContextPackage | None:
        if decision.next_state != "RETRIEVE" or self._context_retriever is None:
            return None
        return self._context_retriever.retrieve(goal)

    def verify_evaluation(
        self,
        query: str,
        result: EvaluationResult,
        *,
        test_refs: list[str],
    ) -> AgentEvaluationResult:
        context = self._retrieve_evaluation_context(query, result)
        evaluation = (
            re_evaluate_with_context(result, context, test_refs=test_refs)
            if context is not None
            else result
        )
        return AgentEvaluationResult(
            evaluation=evaluation,
            route=route_evaluation(evaluation, audit_store=self._audit_store),
            context=context,
        )

    def resume_evaluation(
        self,
        result: EvaluationResult,
        resolution: ConfirmationResolution,
        *,
        task_id: str | None = None,
    ) -> AgentEvaluationResult:
        evaluation = re_evaluate_after_confirmation(result, resolution)
        route = route_evaluation(evaluation, audit_store=self._audit_store)
        self._record_evaluation_confirmation(resolution, route, task_id)
        return AgentEvaluationResult(evaluation=evaluation, route=route)

    def evaluate_observation(
        self,
        observation: ObservationEvaluationInput,
        *,
        retry_count: int,
        evidence: EvaluationEvidence | None = None,
        task_id: str | None = None,
    ) -> AgentEvaluationResult:
        evaluation = evaluate_observation(
            observation,
            retry_count=retry_count,
            evidence=evidence,
        )
        route = route_evaluation(evaluation, audit_store=self._audit_store)
        self._record_observation_route(route, task_id)
        return AgentEvaluationResult(evaluation=evaluation, route=route)

    def _retrieve_evaluation_context(
        self,
        query: str,
        result: EvaluationResult,
    ) -> ContextPackage | None:
        if result.decision != "verify" or self._context_retriever is None:
            return None
        return self._context_retriever.retrieve(query)

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

    def _record_evaluation_confirmation(
        self,
        resolution: ConfirmationResolution,
        route: EvaluationRoute,
        task_id: str | None,
    ) -> None:
        if self._audit_store is not None:
            self._audit_store.append(
                make_audit_event(
                    "evaluation.confirmation",
                    resolution.next_state,
                    resolution.decision,
                )
            )
        if (
            task_id is not None
            and self._run_store is not None
            and resolution.next_state == "RESUME_AGENT_RUN"
        ):
            self._run_store.mark_running(
                task_id,
                decision=route.decision,
                next_state=route.next_state,
            )

    def _record_observation_route(
        self,
        route: EvaluationRoute,
        task_id: str | None,
    ) -> None:
        if task_id is None or self._run_store is None:
            return
        if route.decision == "finish":
            self._run_store.mark_succeeded(task_id)
            return
        self._run_store.mark_running(
            task_id,
            decision=route.decision,
            next_state=route.next_state,
        )

    @staticmethod
    def _status_for_decision(decision: PlanGateDecision) -> str:
        status_by_decision = {
            "continue": "planned",
            "ask_user": "waiting_user",
            "stop": "stopped",
        }
        return status_by_decision[decision.decision]
