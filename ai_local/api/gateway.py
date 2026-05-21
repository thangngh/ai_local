from uuid import uuid4

from fastapi import FastAPI, HTTPException

from ai_local.agent.state import AgentRun
from ai_local.agent.store import InMemoryAgentRunStore
from ai_local.api.schemas import TaskCreate, TaskCreated, TaskState
from ai_local.queue.models import Job
from ai_local.queue.store import InMemoryQueueStore


def enqueue_task(
    task: TaskCreate,
    queue_store: InMemoryQueueStore,
    run_store: InMemoryAgentRunStore,
) -> TaskCreated:
    task_id = f"task_{uuid4().hex}"
    run_store.create(AgentRun(id=task_id, goal=task.goal, project_id=task.project_id))
    queue_store.enqueue(
        Job(
            id=task_id,
            type="agent_run",
            payload={"goal": task.goal, "project_id": task.project_id},
        )
    )
    return TaskCreated(task_id=task_id, status="pending")


def read_task_state(task_id: str, run_store: InMemoryAgentRunStore) -> TaskState | None:
    run = run_store.get(task_id)
    if run is None:
        return None
    return TaskState(
        task_id=run.id,
        goal=run.goal,
        project_id=run.project_id,
        status=run.status,
        decision=run.decision,
        next_state=run.next_state,
        plan=run.plan,
    )


def create_gateway(
    queue_store: InMemoryQueueStore | None = None,
    run_store: InMemoryAgentRunStore | None = None,
) -> FastAPI:
    app = FastAPI(title="AI Local Infrastructure")
    queue = queue_store or InMemoryQueueStore()
    runs = run_store or InMemoryAgentRunStore()
    app.state.queue_store = queue
    app.state.run_store = runs

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tasks", response_model=TaskCreated, status_code=202)
    def create_task(task: TaskCreate) -> TaskCreated:
        return enqueue_task(task, queue, runs)

    @app.get("/tasks/{task_id}", response_model=TaskState)
    def read_task(task_id: str) -> TaskState:
        task_state = read_task_state(task_id, runs)
        if task_state is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task_state

    return app


app = create_gateway()
