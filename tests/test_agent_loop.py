from pathlib import Path

from ai_local.agent.loop import AgentLoop
from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import InMemoryAgentRunStore
from ai_local.audit.store import InMemoryAuditStore
from ai_local.confirmation.manager import resolve_confirmation
from ai_local.evaluator.models import EvaluationEvidence, ObservationEvaluationInput
from ai_local.evaluator.models import EvaluationScore
from ai_local.evaluator.service import evaluate
from ai_local.indexer.models import IndexedChunk
from ai_local.indexer.project import ProjectRetriever
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.planner.gate import decide_plan
from ai_local.planner.models import PlanGateSignals, PlanItem
from ai_local.planner.service import plan_from_goal
from ai_local.retrieval.models import ContextPackage, RetrievalQuery
from ai_local.retrieval.retriever import retrieve_chunks


def test_planner_builds_requirement_analysis_plan() -> None:
    plan = plan_from_goal("  Add task intake  ")

    assert len(plan) == 1
    assert plan[0].intent == "Analyze requirement: Add task intake"
    assert plan[0].required_tools == ["requirements.extract"]


def test_agent_loop_plans_once_from_task_goal() -> None:
    result = AgentLoop().run_once("task_1", "Add request lifecycle")

    assert result.status == "planned"
    assert result.message == "Task task_1 plan gate decided continue"
    assert result.plan[0].intent == "Analyze requirement: Add request lifecycle"
    assert result.decision.next_state == "RETRIEVE"


def test_agent_loop_marks_stored_run_planned() -> None:
    run_store = InMemoryAgentRunStore()
    run_store.create(AgentRun(id="task_2", goal="Add task state"))

    AgentLoop(run_store).run_once("task_2", "Add task state")
    run = run_store.get("task_2")

    assert run is not None
    assert run.status == AgentRunStatus.PLANNED
    assert run.plan[0].intent == "Analyze requirement: Add task state"
    assert run.decision == "continue"
    assert run.next_state == "RETRIEVE"


def test_plan_gate_asks_user_for_ambiguous_plan_signal() -> None:
    decision = decide_plan([PlanItem(intent="Clarify task")], PlanGateSignals(ambiguity=True))

    assert decision.decision == "ask_user"
    assert decision.next_state == "ASK_USER"


def test_agent_loop_stops_unsafe_plan_and_records_state() -> None:
    run_store = InMemoryAgentRunStore()
    run_store.create(AgentRun(id="task_3", goal="Run unsafe plan"))

    result = AgentLoop(run_store).run_once("task_3", "Run unsafe plan", PlanGateSignals(unsafe=True))
    run = run_store.get("task_3")

    assert result.status == "stopped"
    assert result.decision.next_state == "STOP"
    assert run is not None
    assert run.status == AgentRunStatus.STOPPED
    assert run.decision == "stop"


def test_agent_loop_retrieves_context_after_retrieve_plan_gate() -> None:
    class StaticRetriever:
        def retrieve(self, query: str) -> ContextPackage:
            return ContextPackage(
                query=RetrievalQuery(raw=query, normalized=query.lower(), aliases=[query.lower()]),
                hits=[],
                selected_hits=[],
                rejected_hits=[],
                decision="verify",
                reason="configured retrieval dependency",
            )

    result = AgentLoop(context_retriever=StaticRetriever()).run_once(
        "task_4",
        "Use retrieval context",
    )

    assert result.decision.next_state == "RETRIEVE"
    assert result.context is not None
    assert result.context.query.raw == "Use retrieval context"


def test_agent_loop_uses_project_retriever_runtime_path(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("retrieval project evidence\n", encoding="utf-8")
    retriever = ProjectRetriever(tmp_path, KnowledgeIndexStore(tmp_path / "knowledge.db"))

    result = AgentLoop(context_retriever=retriever).run_once(
        "task_5",
        "retrieval project evidence",
    )

    assert result.context is not None
    assert result.context.decision == "continue"
    assert result.context.evidence_refs == ["notes.md:1-1"]


def _score(**overrides: float) -> EvaluationScore:
    values = {
        "correctness": 1.0,
        "completeness": 1.0,
        "evidence_quality": 1.0,
        "requirement_match": 1.0,
        "test_status": 1.0,
        "ambiguity": 0.1,
        "risk": 0.1,
    }
    values.update(overrides)
    return EvaluationScore(**values)


def test_agent_loop_verifies_evaluation_with_runtime_retrieval_and_audit() -> None:
    class EvaluationRetriever:
        def retrieve(self, query: str) -> ContextPackage:
            return retrieve_chunks(
                query,
                [
                    IndexedChunk(
                        file_path="docs/evaluation.md",
                        chunk_type="doc",
                        start_line=7,
                        end_line=9,
                        content="evaluation evidence from agent loop",
                        content_hash="eval-runtime",
                        evidence_strength=0.9,
                    )
                ],
            )

    audit = InMemoryAuditStore()
    result = AgentLoop(context_retriever=EvaluationRetriever(), audit_store=audit).verify_evaluation(
        "evaluation evidence",
        evaluate(_score(evidence_quality=0.2), retry_count=0),
        test_refs=["pytest:tests/test_agent_loop.py"],
    )

    assert result.context is not None
    assert result.evaluation.decision == "accept"
    assert result.route.next_state == "DECISION_GATE"
    assert result.evaluation.evidence.context_refs == ["docs/evaluation.md:7-9"]
    assert audit.list_events()[0].result == "accept"


def test_agent_loop_does_not_promote_memory_conflict_after_context_verify() -> None:
    class MemoryConflictRetriever:
        def retrieve(self, query: str) -> ContextPackage:
            return retrieve_chunks(
                query,
                [
                    IndexedChunk(
                        file_path="docs/memory.md",
                        chunk_type="doc",
                        start_line=2,
                        end_line=3,
                        content="memory evidence conflict remains unresolved",
                        content_hash="memory-conflict",
                        evidence_strength=0.9,
                    )
                ],
            )

    result = AgentLoop(context_retriever=MemoryConflictRetriever()).verify_evaluation(
        "memory evidence conflict",
        evaluate(_score(), retry_count=0, security_signal="memory_conflict"),
        test_refs=["pytest:tests/test_agent_loop.py"],
    )

    assert result.context is not None
    assert result.evaluation.decision == "verify"
    assert result.route.next_state == "VERIFY_EVIDENCE"


def test_agent_loop_resumes_evaluation_after_confirmed_ambiguity() -> None:
    run_store = InMemoryAgentRunStore()
    run_store.create(AgentRun(id="task_confirm", goal="Choose index cleanup mode"))
    audit = InMemoryAuditStore()
    ambiguous = evaluate(
        _score(ambiguity=0.75),
        retry_count=0,
        evidence=EvaluationEvidence(
            context_refs=["docs/decision.md:5-7"],
            test_refs=["pytest:tests/test_agent_loop.py"],
        ),
    )

    result = AgentLoop(run_store=run_store, audit_store=audit).resume_evaluation(
        ambiguous,
        resolve_confirmation(trigger="user_confirmed_fact"),
        task_id="task_confirm",
    )
    run = run_store.get("task_confirm")

    assert result.evaluation.decision == "accept"
    assert result.route.next_state == "DECISION_GATE"
    assert result.evaluation.evidence.decision_refs == [
        "confirmation:save_fact_and_resume"
    ]
    assert run is not None
    assert run.status == AgentRunStatus.RUNNING
    assert run.next_state == "DECISION_GATE"
    assert [event.action for event in audit.list_events()] == [
        "evaluation.decision",
        "evaluation.confirmation",
    ]


def test_agent_loop_keeps_conflicting_confirmation_waiting() -> None:
    ambiguous = evaluate(_score(ambiguity=0.75), retry_count=0)

    result = AgentLoop().resume_evaluation(
        ambiguous,
        resolve_confirmation(trigger="conflicting_answer"),
    )

    assert result.evaluation.decision == "ask_user"
    assert result.route.next_state == "ASK_USER"


def test_agent_loop_resumed_evaluation_still_verifies_missing_evidence() -> None:
    ambiguous = evaluate(_score(ambiguity=0.75), retry_count=0)

    result = AgentLoop().resume_evaluation(
        ambiguous,
        resolve_confirmation(trigger="confirmed_policy"),
    )

    assert result.evaluation.decision == "accept"
    assert result.route.decision == "verify"
    assert result.route.next_state == "VERIFY_EVIDENCE"


def test_agent_loop_routes_repeated_observation_back_to_plan() -> None:
    run_store = InMemoryAgentRunStore()
    run_store.create(AgentRun(id="task_repeat", goal="Stop repeating a failed search"))

    result = AgentLoop(run_store=run_store).evaluate_observation(
        ObservationEvaluationInput(
            tool_name="shell.rg_search",
            tool_status="succeeded",
            output_present=True,
            repeated_action_count=3,
        ),
        retry_count=1,
        task_id="task_repeat",
    )
    run = run_store.get("task_repeat")

    assert result.evaluation.decision == "replan"
    assert result.route.next_state == "PLAN"
    assert run is not None
    assert run.status == AgentRunStatus.RUNNING
    assert run.next_state == "PLAN"


def test_agent_loop_finishes_evidenced_observation_and_audits_route() -> None:
    run_store = InMemoryAgentRunStore()
    run_store.create(AgentRun(id="task_finish", goal="Finish task with evidence"))
    audit = InMemoryAuditStore()

    result = AgentLoop(run_store=run_store, audit_store=audit).evaluate_observation(
        ObservationEvaluationInput(
            tool_name="shell.pytest",
            tool_status="succeeded",
            output_present=True,
            completion_ready=True,
        ),
        retry_count=0,
        evidence=EvaluationEvidence(
            context_refs=["tool:shell.pytest"],
            test_refs=["pytest:tests/test_agent_loop.py"],
        ),
        task_id="task_finish",
    )
    run = run_store.get("task_finish")

    assert result.evaluation.decision == "finish"
    assert result.route.next_state == "DONE"
    assert run is not None
    assert run.status == AgentRunStatus.SUCCEEDED
    assert audit.list_events()[0].result == "finish"
