from ai_local.agent.loop import AgentLoop
from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import InMemoryAgentRunStore
from ai_local.agent.thread_control import InMemoryThreadControl
from ai_local.audit.store import InMemoryAuditStore
from ai_local.outbox.dispatcher import OutboxDispatcher
from ai_local.outbox.models import OutboxEvent, OutboxStatus
from ai_local.outbox.store import InMemoryOutboxStore
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.store import InMemoryQueueStore
from ai_local.queue.worker import QueueWorker, make_agent_run_handler


def test_queue_worker_runs_agent_job_and_audits_lifecycle() -> None:
    queue = InMemoryQueueStore()
    runs = InMemoryAgentRunStore()
    audit = InMemoryAuditStore()
    runs.create(AgentRun(id="job_1", goal="Plan from worker"))
    queue.enqueue(Job(id="job_1", type="agent_run", payload={"goal": "Plan from worker"}))

    job = QueueWorker(queue, make_agent_run_handler(AgentLoop(runs)), audit_store=audit).run_one()
    run = runs.get("job_1")

    assert job is not None
    assert job.status == JobStatus.SUCCEEDED
    assert run is not None
    assert run.status == AgentRunStatus.PLANNED
    assert audit.list_events()[0].action == "job.run"


def test_queue_worker_retries_then_dead_letters_failure() -> None:
    queue = InMemoryQueueStore()
    queue.enqueue(Job(id="bad", type="agent_run", payload={}, max_attempts=2))
    worker = QueueWorker(queue, lambda _job: (_ for _ in ()).throw(RuntimeError("fail")))

    first = worker.run_one()
    second = worker.run_one()

    assert first is not None
    assert second is not None
    assert second.status == JobStatus.DEAD_LETTER
    assert second.last_error == "fail"


def test_thread_control_blocks_second_project_write_run() -> None:
    threads = InMemoryThreadControl()

    first = threads.acquire_write("project", "run_1")
    second = threads.acquire_write("project", "run_2")
    released = threads.release_write("project", "run_1")
    third = threads.acquire_write("project", "run_2")

    assert first.acquired
    assert second.decision == "wait_for_write_lock"
    assert second.owner_run_id == "run_1"
    assert released
    assert third.acquired


def test_outbox_holds_approval_and_dispatches_idempotently() -> None:
    outbox = InMemoryOutboxStore()
    audit = InMemoryAuditStore()
    dispatcher = OutboxDispatcher(
        outbox,
        lambda event: {"event_id": event.id, "applied": True},
        audit_store=audit,
    )
    held = outbox.append(
        OutboxEvent(
            id="hold",
            event_type="git.push",
            idempotency_key="push:1",
            payload={},
            requires_approval=True,
        )
    )
    approved = outbox.append(
        OutboxEvent(
            id="write",
            event_type="write_file",
            idempotency_key="write:1",
            payload={"path": "README.md"},
            approved=True,
        )
    )
    duplicate = outbox.append(
        OutboxEvent(
            id="write-dup",
            event_type="write_file",
            idempotency_key="write:1",
            payload={"path": "README.md"},
            approved=True,
        )
    )

    dispatcher.dispatch(held)
    dispatcher.dispatch(approved)
    dispatcher.dispatch(duplicate)

    assert held.status == OutboxStatus.HELD
    assert approved.status == OutboxStatus.DISPATCHED
    assert approved.result["applied"] is True
    assert duplicate.result == {"decision": "dispatch_once"}
    assert len(audit.list_events()) == 3
