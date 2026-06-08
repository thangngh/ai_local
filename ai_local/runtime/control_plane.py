from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import AuditEvent, SQLiteAuditStore
from ai_local.queue.models import JobStatus
from ai_local.queue.store import SQLiteQueueStore


RuntimeHealth = Literal["ok", "warn", "critical"]

_QUEUE_STATUSES = tuple(status.value for status in JobStatus)
_RUN_STATUSES = (
    "pending",
    "planned",
    "waiting_user",
    "stopped",
    "running",
    "succeeded",
    "failed",
    "cancelled",
)


@dataclass(frozen=True)
class RuntimeControlIssue:
    severity: RuntimeHealth
    code: str
    message: str


@dataclass(frozen=True)
class RuntimeControlSnapshot:
    health: RuntimeHealth
    queue_counts: dict[str, int]
    agent_run_counts: dict[str, int]
    audit_event_count: int
    schema_versions: dict[str, int]
    recent_audit_events: list[AuditEvent] = field(default_factory=list)
    issues: list[RuntimeControlIssue] = field(default_factory=list)
    daemon_status: str | None = None
    daemon_pid: int | None = None
    daemon_last_seen_at: str | None = None
    daemon_iterations: int | None = None
    daemon_stop_reason: str | None = None


def build_runtime_control_snapshot(
    *,
    tasks_db: Path,
    audit_db: Path,
    recent_audit_limit: int = 5,
) -> RuntimeControlSnapshot:
    queue = SQLiteQueueStore(tasks_db)
    runs = SQLiteAgentRunStore(tasks_db)
    audit = SQLiteAuditStore(audit_db)

    queue_counts = _normalize_counts(queue.status_counts(), _QUEUE_STATUSES)
    run_counts = _normalize_counts(runs.status_counts(), _RUN_STATUSES)
    audit_events = audit.list_events()
    schema_versions = {
        **queue.schema_versions(),
        **runs.schema_versions(),
        **audit.schema_versions(),
    }
    issues = _runtime_issues(
        queue_counts=queue_counts,
        run_counts=run_counts,
        schema_versions=schema_versions,
    )
    # Load daemon heartbeat if present
    heartbeat_path = Path(tasks_db).parent / "reports" / "daemon-heartbeat.json"
    daemon_status = daemon_pid = daemon_last_seen_at = daemon_iterations = daemon_stop_reason = None
    if heartbeat_path.exists():
        try:
            hb = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            daemon_status = hb.get("status")
            daemon_pid = hb.get("pid")
            daemon_last_seen_at = hb.get("last_seen_at")
            daemon_iterations = hb.get("iterations")
            daemon_stop_reason = hb.get("stop_reason")
        except Exception:
            pass
    return RuntimeControlSnapshot(
        health=_health_from_issues(issues),
        queue_counts=queue_counts,
        agent_run_counts=run_counts,
        audit_event_count=len(audit_events),
        schema_versions=schema_versions,
        recent_audit_events=audit_events[-recent_audit_limit:] if recent_audit_limit > 0 else [],
        issues=issues,
        daemon_status=daemon_status,
        daemon_pid=daemon_pid,
        daemon_last_seen_at=daemon_last_seen_at,
        daemon_iterations=daemon_iterations,
        daemon_stop_reason=daemon_stop_reason,
    )


def render_runtime_control_snapshot(snapshot: RuntimeControlSnapshot) -> str:
    lines = [
        f"RUNTIME_CONTROL health={snapshot.health}",
        "QUEUE " + _format_counts(snapshot.queue_counts),
        "AGENT_RUNS " + _format_counts(snapshot.agent_run_counts),
        f"AUDIT events={snapshot.audit_event_count}",
        "SCHEMA " + _format_schema_versions(snapshot.schema_versions),
    ]
    if snapshot.recent_audit_events:
        lines.append("RECENT_AUDIT")
        for event in snapshot.recent_audit_events:
            lines.append(
                f"- {event.created_at} action={event.action} "
                f"target={event.target} result={event.result}"
            )
    if snapshot.issues:
        lines.append("ISSUES")
        for issue in snapshot.issues:
            lines.append(f"- {issue.severity} {issue.code}: {issue.message}")
    else:
        lines.append("ISSUES none")
    # Daemon heartbeat fields
    if snapshot.daemon_status is not None:
        parts = [f"DAEMON status={snapshot.daemon_status}"]
        if snapshot.daemon_pid is not None:
            parts.append(f"pid={snapshot.daemon_pid}")
        if snapshot.daemon_last_seen_at is not None:
            parts.append(f"last_seen_at={snapshot.daemon_last_seen_at}")
        if snapshot.daemon_iterations is not None:
            parts.append(f"iterations={snapshot.daemon_iterations}")
        if snapshot.daemon_stop_reason is not None:
            parts.append(f"stop_reason={snapshot.daemon_stop_reason}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _runtime_issues(
    *,
    queue_counts: dict[str, int],
    run_counts: dict[str, int],
    schema_versions: dict[str, int],
) -> list[RuntimeControlIssue]:
    issues: list[RuntimeControlIssue] = []
    if queue_counts.get("dead_letter", 0) > 0:
        issues.append(
            RuntimeControlIssue(
                "critical",
                "queue.dead_letter",
                "dead-letter jobs require operator review",
            )
        )
    if run_counts.get("failed", 0) > 0:
        issues.append(
            RuntimeControlIssue(
                "warn",
                "agent_runs.failed",
                "failed agent runs should be inspected before promotion",
            )
        )
    if run_counts.get("waiting_user", 0) > 0:
        issues.append(
            RuntimeControlIssue(
                "warn",
                "agent_runs.waiting_user",
                "agent runs are waiting for confirmation",
            )
        )
    for component in ("queue", "agent_runs", "audit"):
        if schema_versions.get(component) != 1:
            issues.append(
                RuntimeControlIssue(
                    "critical",
                    f"schema.{component}",
                    f"{component} schema is not at expected version 1",
                )
            )
    return issues


def _health_from_issues(issues: list[RuntimeControlIssue]) -> RuntimeHealth:
    if any(issue.severity == "critical" for issue in issues):
        return "critical"
    if issues:
        return "warn"
    return "ok"


def _normalize_counts(counts: dict[str, int], statuses: tuple[str, ...]) -> dict[str, int]:
    normalized = {status: 0 for status in statuses}
    normalized.update(counts)
    return normalized


def _format_counts(counts: dict[str, int]) -> str:
    return " ".join(f"{status}={count}" for status, count in sorted(counts.items()))


def _format_schema_versions(schema_versions: dict[str, int]) -> str:
    return " ".join(
        f"{component}={version}" for component, version in sorted(schema_versions.items())
    )
