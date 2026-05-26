from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import sleep

from ai_local.runtime.control_plane import (
    RuntimeControlSnapshot,
    build_runtime_control_snapshot,
)


@dataclass(frozen=True)
class RuntimeTuiFrame:
    iteration: int
    health: str
    text: str


def render_runtime_tui_frame(snapshot: RuntimeControlSnapshot, *, iteration: int = 1) -> str:
    lines = [
        "AI LOCAL RUNTIME",
        f"FRAME iteration={iteration} health={snapshot.health}",
        "",
        "[queue]",
        _compact_counts(snapshot.queue_counts),
        "",
        "[agent-runs]",
        _compact_counts(snapshot.agent_run_counts),
        "",
        "[schema]",
        _compact_schema(snapshot.schema_versions),
        "",
        "[audit]",
        f"events={snapshot.audit_event_count}",
    ]
    if snapshot.recent_audit_events:
        for event in snapshot.recent_audit_events:
            lines.append(f"- {event.created_at} {event.action} {event.target} {event.result}")
    else:
        lines.append("- none")
    lines.extend(["", "[issues]"])
    if snapshot.issues:
        for issue in snapshot.issues:
            lines.append(f"- {issue.severity} {issue.code}: {issue.message}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def run_runtime_tui_frames(
    *,
    tasks_db: Path,
    audit_db: Path,
    iterations: int = 1,
    refresh_seconds: float = 0,
    recent_audit_limit: int = 5,
) -> list[RuntimeTuiFrame]:
    frames: list[RuntimeTuiFrame] = []
    for index in range(iterations):
        snapshot = build_runtime_control_snapshot(
            tasks_db=tasks_db,
            audit_db=audit_db,
            recent_audit_limit=recent_audit_limit,
        )
        iteration = index + 1
        frames.append(
            RuntimeTuiFrame(
                iteration=iteration,
                health=snapshot.health,
                text=render_runtime_tui_frame(snapshot, iteration=iteration),
            )
        )
        if index < iterations - 1 and refresh_seconds > 0:
            sleep(refresh_seconds)
    return frames


def _compact_counts(counts: dict[str, int]) -> str:
    active = {key: value for key, value in counts.items() if value}
    if not active:
        return "none"
    return " ".join(f"{key}={value}" for key, value in sorted(active.items()))


def _compact_schema(schema_versions: dict[str, int]) -> str:
    if not schema_versions:
        return "none"
    return " ".join(f"{key}=v{value}" for key, value in sorted(schema_versions.items()))
