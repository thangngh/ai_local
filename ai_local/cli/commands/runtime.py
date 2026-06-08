from __future__ import annotations

import json
import typer
from pathlib import Path

from ai_local.runtime.control_plane import (
    RuntimeControlSnapshot,
    build_runtime_control_snapshot,
    render_runtime_control_snapshot,
)
from ai_local.runtime.worker_contract import ensure_workspace, load_last_worker_result


runtime_app = typer.Typer()


@runtime_app.command("status")
def runtime_status_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    """Print runtime control plane status."""
    paths = ensure_workspace(workspace)
    snapshot = build_runtime_control_snapshot(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo(render_runtime_control_snapshot(snapshot))


def _build_runtime_snapshot_report(
    snapshot: RuntimeControlSnapshot,
    paths: dict[str, Path],
    last_result: dict | None = None,
) -> dict:
    """Build the runtime-snapshot.json report dict from a snapshot."""
    counts = snapshot.queue_counts
    report: dict = {
        "tasks_total": (
            counts.get("pending", 0)
            + counts.get("running", 0)
            + counts.get("succeeded", 0)
            + counts.get("failed", 0)
            + counts.get("cancelled", 0)
            + counts.get("dead_letter", 0)
        ),
        "tasks_pending": counts.get("pending", 0),
        "tasks_done": counts.get("succeeded", 0),
        "tasks_cancelled": counts.get("cancelled", 0),
        "last_worker_result": last_result if last_result is not None else None,
        "logs_dir": str(paths["logs"]),
        "reports_dir": str(paths["reports"]),
    }
    if snapshot.daemon_status is not None:
        report["daemon_status"] = snapshot.daemon_status
    if snapshot.daemon_pid is not None:
        report["daemon_pid"] = snapshot.daemon_pid
    if snapshot.daemon_last_seen_at is not None:
        report["daemon_last_seen_at"] = snapshot.daemon_last_seen_at
    if snapshot.daemon_iterations is not None:
        report["daemon_iterations"] = snapshot.daemon_iterations
    if snapshot.daemon_stop_reason is not None:
        report["daemon_stop_reason"] = snapshot.daemon_stop_reason
    if snapshot.daemon_stale is not None:
        report["daemon_stale"] = snapshot.daemon_stale
    report["daemon_stale_after_seconds"] = snapshot.daemon_stale_after_seconds
    return report


@runtime_app.command("snapshot")
def runtime_snapshot_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    """Snapshot runtime state and write a JSON report."""
    paths = ensure_workspace(workspace)
    snapshot = build_runtime_control_snapshot(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo(render_runtime_control_snapshot(snapshot))

    last_result = load_last_worker_result(workspace)
    report = _build_runtime_snapshot_report(snapshot, paths, last_result)

    snapshot_path = paths["reports"] / "runtime-snapshot.json"
    snapshot_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


@runtime_app.command("logs")
def runtime_logs_group(
    tail: int = typer.Option(None, "--tail"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Print daemon log lines."""
    paths = ensure_workspace(workspace)
    log_path = paths["logs"] / "daemon.log"

    if not log_path.exists():
        typer.echo(f"LOGS none path={log_path}")
        return

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    tail_count = tail if tail is not None else len(lines)
    tail_lines = lines[-tail_count:] if tail_count > 0 else lines

    typer.echo(f"LOGS {log_path} tail={tail_count}")
    for line in tail_lines:
        typer.echo(line)
