from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore, make_audit_event


AgentRunOperationDecision = Literal["succeeded", "denied"]

_STOPPABLE = {
    AgentRunStatus.PENDING,
    AgentRunStatus.PLANNED,
    AgentRunStatus.WAITING_USER,
    AgentRunStatus.RUNNING,
}
_CANCELLABLE = {
    AgentRunStatus.PENDING,
    AgentRunStatus.PLANNED,
    AgentRunStatus.WAITING_USER,
}


@dataclass(frozen=True)
class AgentRunOperationResult:
    decision: AgentRunOperationDecision
    reason: str
    run: AgentRun | None = None
    audit_action: str | None = None


def list_agent_runs(*, tasks_db: Path) -> list[AgentRun]:
    return SQLiteAgentRunStore(tasks_db).list_runs()


def stop_agent_run(
    *,
    tasks_db: Path,
    audit_db: Path,
    run_id: str,
) -> AgentRunOperationResult:
    store = SQLiteAgentRunStore(tasks_db)
    audit = SQLiteAuditStore(audit_db)
    schema_error = _schema_error(store)
    if schema_error is not None:
        return _audit_denial(audit, "agent_run.stop", run_id, schema_error)

    run = store.get(run_id)
    if run is None:
        return _audit_denial(audit, "agent_run.stop", run_id, "agent run does not exist")
    if run.status not in _STOPPABLE:
        return _audit_denial(
            audit,
            "agent_run.stop",
            run_id,
            "agent run cannot be stopped from its current state",
        )

    stopped = store.replace(
        AgentRun(
            id=run.id,
            goal=run.goal,
            project_id=run.project_id,
            status=AgentRunStatus.STOPPED,
            plan=list(run.plan),
            decision="stop",
            next_state="STOP",
        )
    )
    audit.append(make_audit_event("agent_run.stop", run_id, "succeeded"))
    return AgentRunOperationResult(
        decision="succeeded",
        reason="agent run stopped",
        run=stopped,
        audit_action="agent_run.stop",
    )


def cancel_agent_run(
    *,
    tasks_db: Path,
    audit_db: Path,
    run_id: str,
) -> AgentRunOperationResult:
    store = SQLiteAgentRunStore(tasks_db)
    audit = SQLiteAuditStore(audit_db)
    schema_error = _schema_error(store)
    if schema_error is not None:
        return _audit_denial(audit, "agent_run.cancel", run_id, schema_error)

    run = store.get(run_id)
    if run is None:
        return _audit_denial(audit, "agent_run.cancel", run_id, "agent run does not exist")
    if run.status not in _CANCELLABLE:
        return _audit_denial(
            audit,
            "agent_run.cancel",
            run_id,
            "agent run cannot be cancelled from its current state",
        )

    cancelled = store.replace(
        AgentRun(
            id=run.id,
            goal=run.goal,
            project_id=run.project_id,
            status=AgentRunStatus.CANCELLED,
            plan=list(run.plan),
            decision="cancel",
            next_state="CANCELLED",
        )
    )
    audit.append(make_audit_event("agent_run.cancel", run_id, "succeeded"))
    return AgentRunOperationResult(
        decision="succeeded",
        reason="agent run cancelled",
        run=cancelled,
        audit_action="agent_run.cancel",
    )


def _schema_error(store: SQLiteAgentRunStore) -> str | None:
    versions = store.schema_versions()
    if versions.get("agent_runs") != SQLiteAgentRunStore.TARGET_VERSION:
        return "agent_runs schema is not at supported version"
    return None


def _audit_denial(
    audit: SQLiteAuditStore,
    action: str,
    run_id: str,
    reason: str,
) -> AgentRunOperationResult:
    audit.append(make_audit_event(action, run_id, "denied"))
    return AgentRunOperationResult(
        decision="denied",
        reason=reason,
        audit_action=action,
    )
