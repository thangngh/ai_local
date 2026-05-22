from pathlib import Path

from ai_local.agent.loop import AgentLoop
from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import InMemoryAgentRunStore
from ai_local.indexer.project import ProjectRetriever
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.planner.gate import decide_plan
from ai_local.planner.models import PlanGateSignals, PlanItem
from ai_local.planner.service import plan_from_goal
from ai_local.retrieval.models import ContextPackage, RetrievalQuery


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
