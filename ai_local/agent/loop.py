from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.confirmation.models import ConfirmationResolution
from ai_local.evaluator.models import (
    EvaluationEvidence,
    EvaluationResult,
    EvaluationRoute,
    EvaluationScore,
    ObservationEvaluationInput,
)
from ai_local.evaluator.service import (
    evaluate_observation,
    re_evaluate_after_confirmation,
    re_evaluate_with_context,
    route_evaluation,
)
from ai_local.llm.ollama import OllamaClient
from ai_local.planner.gate import PlanGateDecision, decide_plan
from ai_local.planner.models import PlanGateSignals
from ai_local.planner.models import PlanItem
from ai_local.planner.service import plan_from_goal
from ai_local.retrieval.models import ContextPackage
from ai_local.retrieval.vector import TextEmbedder
from ai_local.skills.evidence import script_result_to_evidence
from ai_local.skills.models import (
    SkillRuntimeEvidenceHandoff,
    SkillScriptRunRequest,
    SkillScriptRunResult,
)


class SkillRuntime(Protocol):
    def run(self, request: SkillScriptRunRequest) -> SkillScriptRunResult: ...


class ContextRetriever(Protocol):
    def retrieve(self, query: str) -> ContextPackage: ...


class AgentRunStore(Protocol):
    def mark_planned(self, run_id: str, plan: list[PlanItem]) -> object: ...

    def mark_waiting_user(self, run_id: str, plan: list[PlanItem]) -> object: ...

    def mark_stopped(self, run_id: str, plan: list[PlanItem]) -> object: ...

    def mark_running(self, run_id: str, *, decision: str, next_state: str) -> object: ...

    def mark_succeeded(self, run_id: str) -> object: ...


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


@dataclass(frozen=True)
class AgentSkillRuntimeResult:
    script_result: SkillScriptRunResult
    handoff: SkillRuntimeEvidenceHandoff
    evaluation: EvaluationResult
    route: EvaluationRoute


class AgentLoop:
    def __init__(
        self,
        run_store: AgentRunStore | None = None,
        context_retriever: ContextRetriever | None = None,
        audit_store: InMemoryAuditStore | None = None,
        skill_runtime: SkillRuntime | None = None,
        ollama_client: OllamaClient | None = None,
        embedder: TextEmbedder | None = None,
    ) -> None:
        self._run_store = run_store
        self._context_retriever = context_retriever
        self._audit_store = audit_store
        self._skill_runtime = skill_runtime
        self._ollama_client = ollama_client
        self._embedder = embedder

    def run_once(
        self,
        task_id: str,
        goal: str,
        signals: PlanGateSignals | None = None,
    ) -> AgentLoopResult:
        plan = plan_from_goal(goal, ollama_client=self._ollama_client)
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

    def execute_skill_runtime(
        self,
        request: SkillScriptRunRequest,
        *,
        retry_count: int,
        task_id: str | None = None,
        completion_ready: bool = False,
    ) -> AgentSkillRuntimeResult:
        if self._skill_runtime is None:
            script_result = SkillScriptRunResult(
                package_id=request.script.package.package_id,
                script_id=request.script.script_id,
                tool_name=request.script.tool_name,
                decision="denied",
                reason="skill runtime is not configured",
                next_gate="tool_registry",
            )
        else:
            script_result = self._skill_runtime.run(request)
        handoff = script_result_to_evidence(
            script_result,
            audit_events=self._audit_store.list_events() if self._audit_store is not None else None,
        )
        evaluation = self._evaluate_skill_handoff(
            script_result,
            handoff,
            retry_count=retry_count,
            completion_ready=completion_ready,
        )
        route = route_evaluation(evaluation, audit_store=self._audit_store)
        self._record_observation_route(route, task_id)
        return AgentSkillRuntimeResult(
            script_result=script_result,
            handoff=handoff,
            evaluation=evaluation,
            route=route,
        )

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

    def _evaluate_skill_handoff(
        self,
        script_result: SkillScriptRunResult,
        handoff: SkillRuntimeEvidenceHandoff,
        *,
        retry_count: int,
        completion_ready: bool,
    ) -> EvaluationResult:
        evidence = EvaluationEvidence(
            context_refs=handoff.envelope.evidence_refs,
            test_refs=[f"skill-runtime:{script_result.script_id}"]
            if script_result.decision == "succeeded"
            else [],
            decision_refs=[
                f"skill-runtime:{handoff.decision}",
                f"evidence-rank:{handoff.evidence_band}:{handoff.evidence_rank}",
            ],
        )
        if script_result.decision == "ask_user":
            return EvaluationResult(
                score=EvaluationScore(
                    correctness=0.50,
                    completeness=0.50,
                    evidence_quality=0.40,
                    requirement_match=0.50,
                    test_status=0.0,
                    ambiguity=0.80,
                    risk=0.50,
                ),
                final_score=0.25,
                decision="ask_user",
                retry_count=retry_count,
                reason=script_result.reason,
                evidence=evidence,
            )
        if handoff.decision == "quarantine":
            return evaluate_observation(
                ObservationEvaluationInput(
                    tool_name=script_result.tool_name,
                    tool_status="denied",
                    output_present=False,
                    unsafe_request=True,
                ),
                retry_count=retry_count,
                evidence=evidence,
            )
        if handoff.decision == "stop":
            return EvaluationResult(
                score=EvaluationScore(
                    correctness=0.0,
                    completeness=0.0,
                    evidence_quality=0.0,
                    requirement_match=0.0,
                    test_status=0.0,
                    ambiguity=0.0,
                    risk=1.0,
                ),
                final_score=-0.10,
                decision="stop",
                retry_count=retry_count,
                reason=handoff.reason,
                evidence=evidence,
            )
        return evaluate_observation(
            ObservationEvaluationInput(
                tool_name=script_result.tool_name,
                tool_status=_script_tool_status(script_result),
                output_present=bool(script_result.stdout.strip() or script_result.stderr.strip()),
                completion_ready=completion_ready,
            ),
            retry_count=retry_count,
            evidence=evidence,
        )

    @staticmethod
    def _status_for_decision(decision: PlanGateDecision) -> str:
        status_by_decision = {
            "continue": "planned",
            "ask_user": "waiting_user",
            "stop": "stopped",
        }
        return status_by_decision[decision.decision]


def create_ollama_agent_loop(
    ollama_client: OllamaClient | None = None,
    run_store: AgentRunStore | None = None,
    audit_store: InMemoryAuditStore | None = None,
    skill_runtime: SkillRuntime | None = None,
    embedder: TextEmbedder | None = None,
) -> AgentLoop:
    """Create an AgentLoop pre-configured with Ollama components.

    When ``ollama_client`` is provided, the loop uses:
    - ``OllamaPlanner`` for multi-step planning
    - Real embeddings for semantic retrieval
    When ``ollama_client`` is ``None``, falls back to deterministic stubs.
    """
    context_retriever: ContextRetriever | None = None
    if ollama_client is not None:
        context_retriever = _build_ollama_retriever(ollama_client, embedder=embedder)

    return AgentLoop(
        run_store=run_store,
        context_retriever=context_retriever,
        audit_store=audit_store,
        skill_runtime=skill_runtime,
        ollama_client=ollama_client,
        embedder=embedder,
    )


def _build_ollama_retriever(
    ollama_client: OllamaClient,
    embedder: TextEmbedder | None = None,
) -> ContextRetriever | None:
    """Build a minimal ContextRetriever using Ollama embeddings."""
    from pathlib import Path

    from ai_local.retrieval import create_embedder, create_vector_provider

    embedder_instance = embedder or create_embedder(ollama_client)
    _ = create_vector_provider(embedder_instance)  # available for future use

    class _OllamaContextRetriever:
        """Simple context retriever that uses keyword + semantic search."""

        def __init__(self) -> None:
            self._embedder = embedder_instance

        def retrieve(self, query: str) -> ContextPackage:
            """Retrieve context. Returns an empty package (stub)."""
            from ai_local.retrieval.models import ContextPackage, RetrievalQuery

            q = RetrievalQuery(raw=query, normalized=query.casefold(), aliases=[query])
            return ContextPackage(
                query=q,
                hits=[],
                selected_hits=[],
                rejected_hits=[],
                decision="continue",
                reason="Ollama context retriever stub",
            )

    return _OllamaContextRetriever()


def _script_tool_status(
    result: SkillScriptRunResult,
) -> Literal["accepted", "succeeded", "failed", "denied", "timed_out"]:
    if result.decision == "succeeded":
        return "succeeded"
    if result.decision == "failed":
        return "failed"
    if result.decision == "timed_out":
        return "timed_out"
    if result.decision == "denied":
        return "denied"
    return "denied"
