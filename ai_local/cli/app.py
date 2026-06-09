from __future__ import annotations

import json
from pathlib import Path

import typer
from ai_local.runtime.worker_contract import run_worker_once

# Indexer imports are lazy-loaded within the respective command functions to avoid heavy dependencies at import time.
from ai_local.queue.models import Job
from ai_local.queue.operations import cancel_queue_job
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.backup import create_runtime_backup, restore_runtime_backup

app = typer.Typer()

config_app = typer.Typer()
index_app = typer.Typer()
knowledge_app = typer.Typer()
task_app = typer.Typer()
from ai_local.cli.commands.runtime import runtime_app
from ai_local.cli.commands.worker import worker_app
from ai_local.cli.commands.daemon import daemon_app
from ai_local.cli.commands.demo import demo_app
from ai_local.cli.commands.service import service_app
gate_app = typer.Typer()

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
    """
    if once:
        result = run_worker_once(workspace)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        raise typer.Exit(code=0)

    # ``--loop`` mode (not part of Phase 4A but retained for compatibility)
    while True:
        result = run_worker_once(workspace)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        if not loop:
            break
    raise typer.Exit(code=0)
