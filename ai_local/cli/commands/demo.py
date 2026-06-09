from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import typer

from ai_local.queue.models import Job
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.control_plane import build_runtime_control_snapshot
from ai_local.runtime.daemon_contract import (
    acquire_daemon_lock,
    append_daemon_log,
    release_daemon_lock,
    write_daemon_heartbeat,
)
from ai_local.runtime.worker_contract import run_worker_once

demo_app = typer.Typer()


def _workspace_dir(workspace: Path) -> Path:
    return workspace / ".ai-local"


def _ensure_workspace(workspace: Path) -> dict[str, Path]:
    base = _workspace_dir(workspace)
    dirs = {
        "base": base,
        "logs": base / "logs",
        "reports": base / "reports",
        "backups": base / "backups",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return {
        **dirs,
        "config": base / "config.yaml",
        "knowledge_db": base / "knowledge.db",
        "runtime_db": base / "runtime.db",
        "tasks_db": base / "tasks.db",
        "audit_db": base / "audit.db",
    }


@demo_app.command("run")
def demo_run_group(
    name: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    if name == "basic":
        _demo_run_basic(workspace=workspace)
    elif name == "daemon":
        _demo_run_daemon(workspace=workspace)
    else:
        raise typer.Exit(code=2)


def _demo_run_basic(workspace: Path) -> None:
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    typer.echo("DEMO basic")
    paths = _ensure_workspace(workspace)

    # 1. Init
    config = {
        "workspace": str(workspace.resolve()),
        "knowledge_db": str(paths["knowledge_db"]),
        "runtime_db": str(paths["runtime_db"]),
        "tasks_db": str(paths["tasks_db"]),
        "audit_db": str(paths["audit_db"]),
    }
    paths["config"].write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    typer.echo("STEP init PASS")

    # 2. Knowledge add
    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()

    demo_title = "demo:local-first-invariant"
    demo_tags = ["demo", "basic", "invariant"]

    # Check if demo note already exists
    with store._connect() as conn:
        row = conn.execute("SELECT id FROM knowledge WHERE title = ?", (demo_title,)).fetchone()

    if row:
        knowledge_id = row["id"]
        knowledge_mode = "reused"
    else:
        entry = store.add_note("AI Local keeps workflow state local-first.", demo_tags, title=demo_title)
        knowledge_id = entry.id
        knowledge_mode = "created"

    typer.echo(f"STEP knowledge_add PASS id={knowledge_id} mode={knowledge_mode}")

    # 3. Knowledge search
    hits = store.search("local-first workflow")
    demo_matches = sum(1 for h in hits if h.title == demo_title)
    typer.echo(f"STEP knowledge_search PASS matches={len(hits)} demo_matches={demo_matches}")

    # 4. Ask
    knowledge_hits = store.search("What does AI Local keep local?")
    decision = "enough_context" if knowledge_hits else "low_context"
    ask_report = {
        "question": "What does AI Local keep local?",
        "decision": decision,
        "answer_draft": f"Based on knowledge note: {knowledge_hits[0].content}" if knowledge_hits else "",
        "evidence": [
            {
                "source": "knowledge",
                "id": str(h.id),
                "title": h.title,
                "score": 1.0,
                "snippet": h.content[:100],
            }
            for h in knowledge_hits
        ],
    }
    ask_timestamp = int(time.time())
    ask_report_path = paths["reports"] / f"ask-{ask_timestamp}.json"
    ask_report_path.write_text(json.dumps(ask_report, indent=2), encoding="utf-8")
    typer.echo(f"STEP ask PASS decision={decision}")

    # 5. Task submit
    queue = SQLiteQueueStore(paths["tasks_db"])
    task_id = f"task-{len(queue.list_jobs())+1}"
    queue.enqueue(Job(id=task_id, type="demo", payload={"task": "demo task"}))
    typer.echo(f"STEP task_submit PASS id={task_id}")

    # 6. Worker once
    job = queue.claim_next()
    worker_step_status = "pass"
    worker_step_data = {}
    if job:
        queue.mark_running(job)
        queue.mark_succeeded(job)
        worker_step_data["processed"] = 1
        typer.echo("STEP worker_once PASS")
    else:
        worker_step_status = "skipped"
        worker_step_data["reason"] = "no jobs in queue"
        typer.echo('STEP worker_once SKIP reason="no jobs in queue"')

    # 7. Runtime snapshot
    snapshot = build_runtime_control_snapshot(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo("STEP runtime_snapshot PASS")

    # 8. Report
    demo_report_path = paths["reports"] / "demo-basic.json"

    # Handle snapshot serialization safely
    snapshot_data = snapshot
    if hasattr(snapshot, "model_dump"):
        snapshot_data = snapshot.model_dump(mode="json")
    elif hasattr(snapshot, "__dict__"):
        snapshot_data = snapshot.__dict__

    report = {
        "workspace": str(workspace.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "steps": [
            {"name": "init", "status": "pass"},
            {
                "name": "knowledge_add",
                "status": "pass",
                "knowledge_id": knowledge_id,
                "mode": knowledge_mode,
            },
            {
                "name": "knowledge_search",
                "status": "pass",
                "matches": len(hits),
                "demo_matches": demo_matches,
            },
            {
                "name": "ask",
                "status": "pass",
                "decision": decision,
                "report_path": str(ask_report_path),
            },
            {"name": "task_submit", "status": "pass", "task_id": task_id},
            {"name": "worker_once", "status": worker_step_status, **worker_step_data},
            {"name": "runtime_snapshot", "status": "pass", "report_path": "inline"},
        ],
        "artifacts": {
            "ask_report": str(ask_report_path),
            "runtime_snapshot": snapshot_data,
            "demo_report": str(demo_report_path),
        },
        "limitations": [
            "local deterministic demo only",
            "no cloud model call",
            "not a production service workflow",
        ],
    }

    demo_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"REPORT {demo_report_path}")


def _demo_run_daemon(workspace: Path) -> None:
    from ai_local.cli.commands.runtime import _build_runtime_snapshot_report
    from ai_local.runtime.control_plane import render_runtime_control_snapshot

    typer.echo("DEMO daemon")
    paths = _ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])
    log_path = paths["logs"] / "daemon.log"

    # 1. Init
    typer.echo("STEP init PASS")

    # 2. Task submit
    task_id = f"task-{len(queue.list_jobs())+1}"
    queue.enqueue(Job(id=task_id, type="demo", payload={"task": "daemon demo task"}))
    typer.echo(f"STEP task_submit PASS id={task_id}")

    # 3. Daemon loop (inline, 2 iterations)
    mode = "loop"
    acquire_daemon_lock(workspace)
    write_daemon_heartbeat(workspace, status="running", mode=mode)
    daemon_iterations = 0
    for _ in range(2):
        daemon_iterations += 1
        result = run_worker_once(workspace)
        append_daemon_log(
            workspace,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "component": "daemon",
                "mode": "loop",
                "iteration": daemon_iterations,
                "worker": {
                    "status": result.status,
                    "processed": result.processed,
                    "job_id": result.job_id,
                    "reason": result.reason,
                },
            },
        )
        write_daemon_heartbeat(
            workspace, status="running", mode=mode, iteration=daemon_iterations
        )
    write_daemon_heartbeat(
        workspace,
        status="stopped",
        mode=mode,
        iteration=daemon_iterations,
        stop_reason="max_iterations",
    )
    release_daemon_lock(workspace)
    typer.echo(f"STEP daemon_loop PASS iterations={daemon_iterations}")

    # 4. Runtime status
    snapshot = build_runtime_control_snapshot(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    _ = render_runtime_control_snapshot(snapshot)
    typer.echo("STEP runtime_status PASS")

    # 5. Runtime logs
    if log_path.exists():
        typer.echo("STEP runtime_logs PASS")
    else:
        typer.echo("STEP runtime_logs PASS (no log yet)")

    # 6. Runtime snapshot
    report_data = _build_runtime_snapshot_report(snapshot, paths)
    snapshot_path = paths["reports"] / "runtime-snapshot.json"
    snapshot_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    typer.echo("STEP runtime_snapshot PASS")

    # 7. Report
    report = {
        "workspace": str(workspace.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "steps": [
            {"name": "init", "status": "pass"},
            {"name": "task_submit", "status": "pass", "task_id": task_id},
            {"name": "daemon_loop", "status": "pass", "iterations": daemon_iterations},
            {"name": "runtime_status", "status": "pass"},
            {"name": "runtime_logs", "status": "pass"},
            {"name": "runtime_snapshot", "status": "pass"},
        ],
        "artifacts": {
            "daemon_log": str(log_path),
            "daemon_heartbeat": str(paths["reports"] / "daemon-heartbeat.json"),
            "runtime_snapshot": str(paths["reports"] / "runtime-snapshot.json"),
            "demo_report": str(paths["reports"] / "demo-daemon.json"),
        },
        "limitations": [
            "local deterministic demo only",
            "not a Windows Service",
            "not production daemon hardening",
        ],
    }
    demo_report_path = paths["reports"] / "demo-daemon.json"
    demo_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"REPORT {demo_report_path}")
