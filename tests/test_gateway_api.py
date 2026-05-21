from ai_local.agent.loop import AgentLoop
from ai_local.agent.state import AgentRun
from ai_local.agent.store import InMemoryAgentRunStore
from ai_local.api.gateway import enqueue_task, read_task_state
from ai_local.api.schemas import TaskCreate
from ai_local.queue.models import JobStatus
from ai_local.queue.store import InMemoryQueueStore


def test_gateway_enqueues_agent_run_for_task_intake() -> None:
    queue_store = InMemoryQueueStore()
    run_store = InMemoryAgentRunStore()

    created = enqueue_task(
        TaskCreate(goal="Build request intake", project_id="core"),
        queue_store,
        run_store,
    )
    claimed = queue_store.claim_next()
    task_state = read_task_state(created.task_id, run_store)

    assert created.status == "pending"
    assert created.task_id.startswith("task_")
    assert claimed is not None
    assert claimed.id == created.task_id
    assert claimed.type == "agent_run"
    assert claimed.status == JobStatus.CLAIMED
    assert claimed.payload == {"goal": "Build request intake", "project_id": "core"}
    assert task_state is not None
    assert task_state.task_id == created.task_id
    assert task_state.goal == "Build request intake"
    assert task_state.status == "pending"


def test_gateway_read_returns_none_for_unknown_task() -> None:
    assert read_task_state("missing", InMemoryAgentRunStore()) is None


def test_gateway_state_exposes_plan_gate_decision() -> None:
    run_store = InMemoryAgentRunStore()
    run_store.create(AgentRun(id="task_4", goal="Plan lifecycle"))

    AgentLoop(run_store).run_once("task_4", "Plan lifecycle")
    task_state = read_task_state("task_4", run_store)

    assert task_state is not None
    assert task_state.status == "planned"
    assert task_state.decision == "continue"
    assert task_state.next_state == "RETRIEVE"
    assert task_state.plan[0].required_tools == ["requirements.extract"]
