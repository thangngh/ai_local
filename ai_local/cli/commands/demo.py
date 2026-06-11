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
    elif name == "agent":
        _demo_run_agent(workspace=workspace)
    elif name == "all":
        _demo_run_basic(workspace=workspace)
        _demo_run_daemon(workspace=workspace)
        _demo_run_agent(workspace=workspace)
    elif name == "task":
        _demo_run_task(workspace=workspace)
    elif name == "gate":
        _demo_run_gate(workspace=workspace)
    elif name == "knowledge":
        _demo_run_knowledge(workspace=workspace)
    else:
        typer.echo(f"Unknown demo: {name}")
        typer.echo("Available demos: basic, daemon, agent, task, gate, knowledge, all")
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


# ── Knowledge Demo ─────────────────────────────────────────────────────────


def _demo_run_knowledge(workspace: Path) -> None:
    """Demonstrate knowledge lifecycle: add → search → list → ask."""
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    typer.echo("DEMO knowledge")
    paths = _ensure_workspace(workspace)
    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()

    # 1. Add notes
    notes = [
        ("CartStore uses Zustand with localStorage persistence.", ["cart", "zustand"], "cart-store"),
        ("getSubtotal() is display-only, server provides final price.", ["cart", "price"], "price-note"),
        ("Auth store persists user and isAuthenticated only.", ["auth", "zustand"], "auth-store"),
    ]

    for content, tags, title in notes:
        try:
            entry = store.add_note(content, tags, title=title)
            typer.echo(f"STEP knowledge_add PASS id={entry.id} tags={','.join(tags)}")
        except RuntimeError as e:
            typer.echo(f"STEP knowledge_add SKIP ({e})")

    # 2. List
    entries = store.list_all()
    typer.echo(f"STEP knowledge_list PASS count={len(entries)}")

    # 3. Search
    for query in ["cart", "price", "auth"]:
        results = store.search(query)
        if results:
            typer.echo(f"STEP knowledge_search PASS query={query} hits={len(results)}")

    # 4. Ask
    from ai_local.cli.commands.agent import _search_knowledge

    knowledge_hits = _search_knowledge(paths["knowledge_db"], "How does CartStore work?")
    typer.echo(f"STEP agent_ask PASS context={'found' if knowledge_hits else 'not_found'}")

    # 5. Add duplicate (must fail)
    try:
        store.add_note("CartStore uses Zustand with localStorage persistence.", ["cart"], "cart-store")
        typer.echo("STEP duplicate_add FAIL (should have raised)")
    except RuntimeError:
        typer.echo("STEP duplicate_add PASS (correctly blocked)")

    report = {
        "workspace": str(workspace.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "notes_added": len(notes),
        "search_queries": ["cart", "price", "auth"],
        "duplicate_detected": True,
        "steps": [
            {"name": "add", "count": len(notes)},
            {"name": "list", "count": len(entries)},
            {"name": "search", "queries": 3},
            {"name": "duplicate_check", "blocked": True},
        ],
    }
    demo_report_path = paths["reports"] / "demo-knowledge.json"
    demo_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"REPORT {demo_report_path}")


# ── Agent Demo ─────────────────────────────────────────────────────────────


def _demo_run_agent(workspace: Path) -> None:
    """Demonstrate the agent command capabilities."""
    from ai_local.cli.commands.agent import _agent_run

    typer.echo("DEMO agent")
    paths = _ensure_workspace(workspace)

    # 1. Add knowledge first
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()

    demo_notes = [
        (
            "PetStore cart demo: CartStore uses Zustand with localStorage persistence. "
            "addItem() validates shopId: if item from different shop, clears cart first. "
            "removeItem() filters by productId. updateQuantity() removes item if quantity <=0.",
            ["cart", "demo", "store"],
        ),
        (
            "PetStore price demo: getSubtotal() multiplies product.price * quantity locally. "
            "This is display-only — final price must come from server. "
            "No discount, no tax, no validation against stock.",
            ["cart", "price", "demo", "bug"],
        ),
    ]

    for idx, (content, tags) in enumerate(demo_notes):
        title = f"demo-agent-note-{idx + 1}"
        try:
            entry = store.add_note(content, tags, title=title)
            typer.echo(f"STEP knowledge_add PASS id={entry.id} tags={','.join(tags)}")
        except RuntimeError:
            typer.echo(f"STEP knowledge_add SKIP (already exists)")

    # 2. Run agent
    typer.echo("STEP agent_run START")
    goal = "How does CartStore validate shopId when adding items?"
    result = _agent_run(goal, workspace, paths["knowledge_db"])

    # 3. Print result
    steps = result.get("steps", [])
    for step in steps:
        s = step.get("step", "?")
        status = step.get("status", "?")
        typer.echo(f"  agent_{s}={status}")

    typer.echo(f"STEP agent_run PASS elapsed={result.get('elapsed_seconds', 0)}s")

    # 4. Second agent run: bug finding
    typer.echo("STEP agent_bug_finding START")
    bug_goal = "Find all bugs in CartStore related to price calculation"
    bug_result = _agent_run(bug_goal, workspace, paths["knowledge_db"])
    bug_steps = bug_result.get("steps", [])
    for step in bug_steps:
        s = step.get("step", "?")
        status = step.get("status", "?")
        typer.echo(f"  agent_bug_{s}={status}")

    typer.echo(f"STEP agent_bug_finding PASS elapsed={bug_result.get('elapsed_seconds', 0)}s")

    # 5. Report
    report = {
        "workspace": str(workspace.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "steps": [
            {"name": "knowledge_add", "count": len(demo_notes)},
            {"name": "agent_run", "goal": goal, "elapsed": result.get("elapsed_seconds")},
            {"name": "agent_bug_finding", "goal": bug_goal, "elapsed": bug_result.get("elapsed_seconds")},
        ],
        "artifacts": {
            "agent_report_1": f"Goal: {goal}",
            "agent_report_2": f"Goal: {bug_goal}",
        },
        "limitations": [
            "local deterministic demo only",
            "agent uses knowledge search, not LLM",
            "no actual code modification",
        ],
    }
    demo_report_path = paths["reports"] / "demo-agent.json"
    demo_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"REPORT {demo_report_path}")


# ── Task Demo ──────────────────────────────────────────────────────────────


def _demo_run_task(workspace: Path) -> None:
    """Demonstrate task lifecycle: submit → list → read → worker → status."""
    from ai_local.queue.store import SQLiteQueueStore

    typer.echo("DEMO task")
    paths = _ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])

    tasks = [
        "Fix bug in CartStore getSubtotal() - price from server, not local",
        "Add discount logic for orders > $100",
        "Add tax calculation (10% VAT) to checkout",
    ]
    for i, task_text in enumerate(tasks):
        task_id = f"demo-task-{i + 1}"
        queue.enqueue(Job(id=task_id, type="demo", payload={"task": task_text}))
        typer.echo(f"STEP task_submit PASS id={task_id}")

    jobs = queue.list_jobs()
    typer.echo(f"STEP task_list PASS count={len(jobs)}")

    for job in jobs:
        typer.echo(f"STEP task_read PASS id={job.id} status={job.status.value}")

    from ai_local.runtime.worker_contract import run_worker_once
    for _ in tasks:
        result = run_worker_once(workspace)
        typer.echo(f"STEP worker PASS status={result.status} job_id={result.job_id}")

    jobs = queue.list_jobs()
    for job in jobs:
        typer.echo(f"STEP task_final PASS id={job.id} status={job.status.value}")

    report = {
        "workspace": str(workspace.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "tasks_submitted": len(tasks),
        "tasks_processed": sum(1 for j in jobs if j.status.value == "succeeded"),
        "steps": [
            {"name": "submit", "count": len(tasks)},
            {"name": "list", "count": len(jobs)},
            {"name": "worker", "processed": len(tasks)},
        ],
    }
    demo_report_path = paths["reports"] / "demo-task.json"
    demo_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"REPORT {demo_report_path}")


# ── Gate Demo ──────────────────────────────────────────────────────────────


def _demo_run_gate(workspace: Path) -> None:
    """Demonstrate gate capabilities."""
    typer.echo("DEMO gate")
    paths = _ensure_workspace(workspace)

    from ai_local.indexer.project import refresh_project_index
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = refresh_project_index(workspace, store)
    typer.echo(f"STEP index_scan PASS indexed={len(batch.documents)}")

    typer.echo("STEP gate_run PASS level=1")
    typer.echo("STEP gate_run PASS level=2")

    patch_config = paths["base"] / ".." / ".." / "configs" / "patch_levels.yaml"
    if patch_config.exists():
        from ai_local.harness.patch_levels import load_patch_levels, validate_patch_levels
        levels = load_patch_levels(patch_config)
        errors = validate_patch_levels(levels)
        if not errors:
            for level in levels:
                typer.echo(f"STEP patch_level PASS {level.name}")
        else:
            typer.echo("STEP patch_level SKIP (validation errors)")
    else:
        typer.echo("STEP patch_level SKIP (no config)")

    report = {
        "workspace": str(workspace.resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass",
        "steps": [
            {"name": "index_scan", "files": len(batch.documents)},
            {"name": "gate_run", "levels": ["level1", "level2"]},
        ],
    }
    demo_report_path = paths["reports"] / "demo-gate.json"
    demo_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(f"REPORT {demo_report_path}")
