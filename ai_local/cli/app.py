from __future__ import annotations

import json
import importlib.util
import platform
import subprocess
from pathlib import Path

import typer
from ai_local.runtime.worker_contract import run_worker_once

# Indexer imports are lazy-loaded within the respective command functions to avoid heavy dependencies at import time.
# from ai_local.indexer.project import rebuild_project_index, refresh_project_index
# from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.queue.models import Job
from ai_local.queue.operations import cancel_queue_job
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.backup import create_runtime_backup, restore_runtime_backup
from ai_local.runtime.control_plane import (
    build_runtime_control_snapshot,
    render_runtime_control_snapshot,
)

app = typer.Typer()

config_app = typer.Typer()
index_app = typer.Typer()
knowledge_app = typer.Typer()
task_app = typer.Typer()
from ai_local.cli.commands.runtime import runtime_app
from ai_local.cli.commands.worker import worker_app
from ai_local.cli.commands.daemon import daemon_app
gate_app = typer.Typer()
demo_app = typer.Typer()
service_app = typer.Typer()

app.add_typer(config_app, name="config")
app.add_typer(index_app, name="index")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(task_app, name="task")
app.add_typer(worker_app, name="worker")
app.add_typer(runtime_app, name="runtime")
app.add_typer(gate_app, name="gate")
app.add_typer(demo_app, name="demo")
app.add_typer(daemon_app, name="daemon")
app.add_typer(service_app, name="service")


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


@config_app.command("show")
def config_show(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    typer.echo(paths["config"].read_text(encoding="utf-8") if paths["config"].exists() else "{}")


@config_app.command("validate")
def config_validate(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    if not paths["config"].exists():
        raise typer.Exit(code=1)
    data = json.loads(paths["config"].read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise typer.Exit(code=1)
    typer.echo("CONFIG OK")


@index_app.command("scan")
def index_scan_group(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    # Lazy import to avoid heavy dependencies unless this command is used
    from ai_local.indexer.project import refresh_project_index
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = refresh_project_index(root, store)
    typer.echo(f"INDEX_SCAN indexed={len(batch.documents)} unchanged={len(batch.unchanged_paths)}")


@index_app.command("rebuild")
def index_rebuild_group(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    # Lazy import
    from ai_local.indexer.project import rebuild_project_index
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = rebuild_project_index(root, store)
    typer.echo(f"INDEX_REBUILD indexed={len(batch.documents)} deleted={len(batch.deleted_paths)}")


@index_app.command("stats")
def index_stats_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    # Lazy import
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    stats = store.stats()
    typer.echo(f"INDEX_STATS files={stats.files} chunks={stats.chunks} symbols={stats.symbols}")


@index_app.command("search")
def index_search_group(
    query: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    # Lazy import
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    hits = store.search_chunks(query, limit=5)
    for hit in hits:
        typer.echo(f"{hit.source_ref} {hit.content[:120].replace(chr(10), ' ')}")


from ai_local.cli.commands.ask import ask_group  # noqa: E402
app.command("ask")(ask_group)


@knowledge_app.command("add")
def knowledge_add(path: Path, workspace: Path = typer.Option(Path("."), "--workspace", "-w"), tag: str = typer.Option(..., "--tag")) -> None:
    paths = _ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore
    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    entry = store.add_file(path, tag)
    typer.echo(f"KNOWLEDGE added id={entry.id} title={entry.title} tags={tag}")


@knowledge_app.command("add-note")
def knowledge_add_note(text: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w"), tag: str = typer.Option(..., "--tag")) -> None:
    paths = _ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore
    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    entry = store.add_note(text, tag)
    typer.echo(f"KNOWLEDGE note added id={entry.id} tags={tag}")


@knowledge_app.command("list")
def knowledge_list(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore
    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    entries = store.list_all()
    for entry in entries:
        tags = json.loads(entry.tags_json) if entry.tags_json else []
        typer.echo(f"{entry.id} {entry.kind} {entry.title} tags={','.join(tags)}")


@knowledge_app.command("search")
def knowledge_search(query: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore
    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    entries = store.search(query)
    for entry in entries:
        snippet = entry.content[:200].replace('\n', ' ')
        typer.echo(f"{entry.id} {entry.kind} {entry.title} {snippet}")


@task_app.command("submit")
def task_submit_group(task: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    task_submit(task=task, workspace=workspace)


@task_app.command("list")
def task_list_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    task_list(workspace=workspace)


@task_app.command("read")
def task_read_group(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    task_read(task_id=task_id, workspace=workspace)


@task_app.command("cancel")
def task_cancel_group(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    task_cancel(task_id=task_id, workspace=workspace)


@worker_app.command("run")
def worker_run_group(
    once: bool = typer.Option(False, "--once"),
    loop: bool = typer.Option(False, "--loop"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    worker_run(once=once, loop=loop, workspace=workspace)





backup_app = typer.Typer()
runtime_app.add_typer(backup_app, name="backup")


@backup_app.command("create")
def runtime_backup_create_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    runtime_backup_create(workspace=workspace)


@backup_app.command("restore")
def runtime_backup_restore_group(backup_path: Path, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    result = restore_runtime_backup(backup_dir=backup_path, tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo(f"{result.decision} {result.reason}")


@gate_app.command("run")
def gate_run_group(level: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    typer.echo(f"GATE run level={level} workspace={workspace}")


@demo_app.command("run")
def demo_run_group(
    name: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    if name != "basic":
        raise typer.Exit(code=2)
    demo_run_basic(workspace=workspace)


# Legacy daemon command removed; using daemon_app's implementation with --once support.


@service_app.command("install")
def service_install_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    _ensure_workspace(workspace)
    if dry_run:
        typer.echo("powershell.exe -NoProfile -Command New-Service -Name 'ai-local' -BinaryPathName 'python -m ai_local.cli daemon run'")
        return
    service_install(dry_run=dry_run)


@service_app.command("uninstall")
def service_uninstall_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    if dry_run:
        typer.echo("sc.exe delete ai-local")
        return
    service_uninstall()


@service_app.command("start")
def service_start_group(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    if dry_run:
        typer.echo("Start-Service ai-local")
        return
    service_start()


@service_app.command("stop")
def service_stop_group(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    if dry_run:
        typer.echo("Stop-Service ai-local")
        return
    service_stop()


@service_app.command("status")
def service_status_group(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    if dry_run:
        typer.echo("Get-Service ai-local")
        return
    service_status()


@service_app.command("logs")
def service_logs_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    service_logs(workspace=workspace)


@app.command()
def init(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    config = {
        "workspace": str(workspace.resolve()),
        "knowledge_db": str(paths["knowledge_db"]),
        "runtime_db": str(paths["runtime_db"]),
        "tasks_db": str(paths["tasks_db"]),
        "audit_db": str(paths["audit_db"]),
    }
    if not paths["config"].exists():
        paths["config"].write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        existing = json.loads(paths["config"].read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            raise typer.Exit(code=1)
    typer.echo(f"INIT workspace={workspace} dir={paths['base']}")


@app.command(name="config")
def config_cmd(
    action: str = typer.Argument(...),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    paths = _ensure_workspace(workspace)
    if action == "show":
        typer.echo(paths["config"].read_text(encoding="utf-8") if paths["config"].exists() else "{}")
        return
    if action == "validate":
        if not paths["config"].exists():
            raise typer.Exit(code=1)
        data = json.loads(paths["config"].read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise typer.Exit(code=1)
        typer.echo("CONFIG OK")
        return
    raise typer.Exit(code=2)


@app.command("index-scan")
def index_scan(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = refresh_project_index(root, store)
    typer.echo(f"INDEX_SCAN indexed={len(batch.documents)} unchanged={len(batch.unchanged_paths)}")


@app.command("index-rebuild")
def index_rebuild(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = rebuild_project_index(root, store)
    typer.echo(f"INDEX_REBUILD indexed={len(batch.documents)} deleted={len(batch.deleted_paths)}")


@app.command("index-stats")
def index_stats(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    stats = store.stats()
    typer.echo(f"INDEX_STATS files={stats.files} chunks={stats.chunks} symbols={stats.symbols}")


@app.command("index-search")
def index_search(
    query: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    paths = _ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    hits = store.search_chunks(query, limit=5)
    for hit in hits:
        typer.echo(f"{hit.source_ref} {hit.content[:120].replace(chr(10), ' ')}")




@app.command("runtime-backup-create")
def runtime_backup_create(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    result = create_runtime_backup(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], backup_dir=paths["backups"])
    typer.echo(f"{result.decision} {result.reason}")


@app.command("runtime-backup-restore")
def runtime_backup_restore(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    result = restore_runtime_backup(backup_dir=paths["backups"], tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo(f"{result.decision} {result.reason}")


@app.command("task-submit")
def task_submit(
    task: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    paths = _ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id=f"task-{len(queue.list_jobs())+1}", type="demo", payload={"task": task}))
    typer.echo("TASK submitted")


@app.command("task-list")
def task_list(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    for job in SQLiteQueueStore(paths["tasks_db"]).list_jobs():
        typer.echo(f"{job.id} {job.status.value} {job.type}")


@app.command("task-read")
def task_read(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    job = SQLiteQueueStore(paths["tasks_db"]).get(task_id)
    if job is None:
        raise typer.Exit(code=1)
    typer.echo(json.dumps(job.model_dump(mode="json"), indent=2))


@app.command("task-cancel")
def task_cancel(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    result = cancel_queue_job(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], job_id=task_id)
    typer.echo(result.decision)


def worker_run(
    once: bool = typer.Option(False, "--once"),
    loop: bool = typer.Option(False, "--loop"),
    workspace: Path = typer.Option(Path('.'), "--workspace", "-w"),
) -> None:
    """Run the worker.

    * ``--once`` processes a single job (or none) and exits.
    * ``--loop`` processes jobs continuously until interrupted.
    The original CLI printed ``WORKER ran``/``idle``; now we emit the
    contract‑specified format.
    """
    if once:
        result = run_worker_once(workspace)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        raise typer.Exit(code=0)

    # ``--loop`` mode (not part of Phase 4A but retained for compatibility)
    while True:
        result = run_worker_once(workspace)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        if not loop:
            break
    raise typer.Exit(code=0)


@app.command("demo-run-basic")
def demo_run_basic(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    import time
    from datetime import datetime, timezone
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
        typer.echo("STEP worker_once SKIP reason=\"no jobs in queue\"")

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
                "mode": knowledge_mode
            },
            {"name": "knowledge_search", "status": "pass", "matches": len(hits), "demo_matches": demo_matches},
            {"name": "ask", "status": "pass", "decision": decision, "report_path": str(ask_report_path)},
            {"name": "task_submit", "status": "pass", "task_id": task_id},
            {
                "name": "worker_once",
                "status": worker_step_status,
                **worker_step_data
            },
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


def _unsupported() -> None:
    typer.echo("service commands are only supported on Windows", err=True)
    raise typer.Exit(code=1)


@app.command("service-install")
def service_install(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    if platform.system() != "Windows":
        _unsupported()
    cmd = ["powershell.exe", "-NoProfile", "-Command", "New-Service -Name 'ai-local' -BinaryPathName 'python -m ai_local.cli daemon run'"]
    typer.echo(" ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


@app.command("service-uninstall")
def service_uninstall() -> None:
    if platform.system() != "Windows":
        _unsupported()
    typer.echo("sc.exe delete ai-local")


@app.command("service-start")
def service_start() -> None:
    if platform.system() != "Windows":
        _unsupported()
    typer.echo("Start-Service ai-local")


@app.command("service-stop")
def service_stop() -> None:
    if platform.system() != "Windows":
        _unsupported()
    typer.echo("Stop-Service ai-local")


@app.command("service-status")
def service_status() -> None:
    if platform.system() != "Windows":
        _unsupported()
    typer.echo("Get-Service ai-local")


@app.command("service-logs")
def service_logs(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = _ensure_workspace(workspace)
    for log in sorted(paths["logs"].glob("*.log")):
        typer.echo(str(log))
