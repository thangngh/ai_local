"""AI Local CLI — main entry point."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from ai_local.config.workspace import (
    DEFAULT_OLLAMA_CONFIG,
    ensure_workspace,
    get_ollama_config,
    load_workspace_config,
    save_workspace_config,
    set_ollama_config,
    workspace_dir,
)
from ai_local.runtime.worker_contract import run_worker_once

# Indexer imports are lazy-loaded within the respective command functions
from ai_local.queue.models import Job
from ai_local.queue.operations import cancel_queue_job
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.backup import create_runtime_backup, restore_runtime_backup
from ai_local.runtime.control_plane import build_runtime_control_snapshot
from ai_local.skills.store import (
    InstalledSkillStore,
    cleanup_stale_installed_skills,
    rebuild_installed_skill_registry,
    refresh_installed_skill_registry,
)
from ai_local.queue.operations import (
    cancel_queue_job,
    list_queue_jobs,
    retry_dead_letter_job,
)
from ai_local.agent.operations import (
    cancel_agent_run,
    list_agent_runs,
    stop_agent_run,
)
from ai_local.config.loader import resolve_config
from ai_local.db.schema import list_schema_versions as _list_schema_versions
from ai_local.pipeline.audit_chain import PipelineAuditChainStore
from ai_local.pipeline.phase9_close import run_phase9_close
from ai_local.pipeline.report import run_phase9_integration_report

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
from ai_local.cli.commands.agent import agent_app
gate_app = typer.Typer()
skills_app = typer.Typer()
queue_app = typer.Typer()
phase9_app = typer.Typer()
tui_app = typer.Typer()

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
app.add_typer(agent_app, name="agent")
app.add_typer(skills_app, name="skills")
app.add_typer(queue_app, name="queue")
app.add_typer(phase9_app, name="phase9")
app.add_typer(tui_app, name="tui")


# ── Skills commands ──────────────────────────────────────────────────────


@skills_app.command("refresh")
def skills_refresh(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    root: Path = typer.Option(Path("."), "--root", "-r"),
    skills_db: Path = typer.Option(Path(".ai-local/skills.db"), "--skills-db"),
) -> None:
    """Refresh the installed-skill registry."""
    paths = ensure_workspace(workspace)
    store = InstalledSkillStore(skills_db if skills_db.is_absolute() else paths["base"] / skills_db.name)
    result = refresh_installed_skill_registry(root, store, audit_ref="cli:skills:refresh")
    typer.echo(f"SKILLS refresh upserted={len(result.upserted)} unchanged={len(result.unchanged)} deleted={len(result.deleted)}")


@skills_app.command("cleanup")
def skills_cleanup(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    root: Path = typer.Option(Path("."), "--root", "-r"),
    skills_db: Path = typer.Option(Path(".ai-local/skills.db"), "--skills-db"),
) -> None:
    """Remove stale skill entries from the registry."""
    paths = ensure_workspace(workspace)
    store = InstalledSkillStore(skills_db if skills_db.is_absolute() else paths["base"] / skills_db.name)
    stale = cleanup_stale_installed_skills(root, store)
    typer.echo(f"SKILLS cleanup removed={len(stale)}")


@skills_app.command("rebuild")
def skills_rebuild(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    root: Path = typer.Option(Path("."), "--root", "-r"),
    skills_db: Path = typer.Option(Path(".ai-local/skills.db"), "--skills-db"),
) -> None:
    """Rebuild the entire skill registry from scratch."""
    paths = ensure_workspace(workspace)
    store = InstalledSkillStore(skills_db if skills_db.is_absolute() else paths["base"] / skills_db.name)
    result = rebuild_installed_skill_registry(root, store, audit_ref="cli:skills:rebuild")
    typer.echo(f"SKILLS rebuild upserted={len(result.upserted)} deleted={len(result.deleted)}")


@skills_app.command("stats")
def skills_stats(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    skills_db: Path = typer.Option(Path(".ai-local/skills.db"), "--skills-db"),
) -> None:
    """Show skill registry statistics."""
    paths = ensure_workspace(workspace)
    store = InstalledSkillStore(skills_db if skills_db.is_absolute() else paths["base"] / skills_db.name)
    stats = store.stats(root=paths["base"])
    typer.echo(f"SKILLS packages={stats.packages} trusted={stats.trusted} stale={stats.stale}")


# ── Queue commands ───────────────────────────────────────────────────────


@queue_app.command("jobs")
def queue_jobs(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """List all queue jobs."""
    paths = ensure_workspace(workspace)
    jobs = list_queue_jobs(tasks_db=paths["tasks_db"])
    for job in jobs:
        typer.echo(f"{job.id} {job.status.value} type={job.type} attempts={job.attempts}/{job.max_attempts}")
    if not jobs:
        typer.echo("QUEUE jobs none")


@queue_app.command("retry")
def queue_retry(
    job_id: str = typer.Argument(..., help="Job ID to retry"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Retry a dead-letter queue job."""
    paths = ensure_workspace(workspace)
    result = retry_dead_letter_job(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], job_id=job_id)
    typer.echo(f"QUEUE retry {result.decision} reason=\"{result.reason}\"")
    if result.decision == "denied":
        raise typer.Exit(code=1)


@queue_app.command("cancel")
def queue_cancel(
    job_id: str = typer.Argument(..., help="Job ID to cancel"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Cancel a pending or claimed queue job."""
    paths = ensure_workspace(workspace)
    result = cancel_queue_job(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], job_id=job_id)
    typer.echo(f"QUEUE cancel {result.decision} reason=\"{result.reason}\"")
    if result.decision == "denied":
        raise typer.Exit(code=1)


# ── Agent-run commands (extensions) ──────────────────────────────────────

agent_run_app = typer.Typer()
agent_app.add_typer(agent_run_app, name="runs")


@agent_run_app.command("list")
def agent_runs_list_cmd(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """List all agent runs."""
    paths = ensure_workspace(workspace)
    runs = list_agent_runs(tasks_db=paths["tasks_db"])
    for run in runs:
        typer.echo(f"{run.id} {run.status.value} goal={run.goal[:60]}...")
    if not runs:
        typer.echo("AGENT runs none")


@agent_run_app.command("stop")
def agent_runs_stop_cmd(
    run_id: str = typer.Argument(..., help="Run ID to stop"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Stop a running agent run."""
    paths = ensure_workspace(workspace)
    result = stop_agent_run(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], run_id=run_id)
    typer.echo(f"AGENT run-stop {result.decision} reason=\"{result.reason}\"")
    if result.decision == "denied":
        raise typer.Exit(code=1)


@agent_run_app.command("cancel")
def agent_runs_cancel_cmd(
    run_id: str = typer.Argument(..., help="Run ID to cancel"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Cancel a pending agent run."""
    paths = ensure_workspace(workspace)
    result = cancel_agent_run(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], run_id=run_id)
    typer.echo(f"AGENT run-cancel {result.decision} reason=\"{result.reason}\"")
    if result.decision == "denied":
        raise typer.Exit(code=1)


# ── Runtime extras ───────────────────────────────────────────────────────


@runtime_app.command("store-stats")
def runtime_store_stats_cmd(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Show runtime store statistics (queue, agent runs, audit)."""
    paths = ensure_workspace(workspace)
    snapshot = build_runtime_control_snapshot(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo(f"QUEUE {dict(snapshot.queue_counts)}")
    typer.echo(f"AGENT_RUNS {dict(snapshot.agent_run_counts)}")
    typer.echo(f"AUDIT events={snapshot.audit_event_count}")


@runtime_app.command("schema-versions")
def runtime_schema_versions_cmd(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Show runtime database schema versions."""
    import sqlite3

    paths = ensure_workspace(workspace)
    dbs = {"tasks": paths["tasks_db"], "audit": paths["audit_db"]}
    for name, db_path in dbs.items():
        if not db_path.exists():
            typer.echo(f"SCHEMA {name} absent")
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            versions = _list_schema_versions(conn)
            conn.close()
            if versions:
                for v in versions:
                    typer.echo(f"SCHEMA {name} {v.component}=v{v.version}")
            else:
                typer.echo(f"SCHEMA {name} none")
        except Exception as exc:
            typer.echo(f"SCHEMA {name} error={exc}")


# ── TUI commands ─────────────────────────────────────────────────────────


@tui_app.command("run")
def tui_run_cmd(
    iterations: int = typer.Option(1, "--iterations", "-n"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Run TUI frames to render runtime state."""
    from ai_local.runtime.tui import run_runtime_tui_frames as _run_tui

    paths = ensure_workspace(workspace)
    frames = _run_tui(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], iterations=iterations)
    for frame in frames:
        typer.echo(frame.text)
        if frame.iteration < iterations:
            typer.echo("---")


# ── Phase 9 commands ─────────────────────────────────────────────────────


@phase9_app.command("integration-report")
def phase9_integration_report_cmd(
    scenario: str = typer.Argument("ready", help="ready|no-path|prompt-injection"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    patch_levels_config: Path = typer.Option(Path("configs/patch_levels.yaml"), "--patch-levels-config"),
) -> None:
    """Run Phase 9 integration report for a scenario."""
    paths = ensure_workspace(workspace)
    patch_levels_config = resolve_config(patch_levels_config, "configs/patch_levels.yaml")
    report = run_phase9_integration_report(
        scenario=scenario,  # type: ignore[arg-type]
        workspace_root=paths["base"],
        patch_levels_config=patch_levels_config,
        audit_db=paths["audit_db"],
    )
    typer.echo(f"PHASE9 scenario={scenario} status={report['status']} final_state={report['final_state']}")


@phase9_app.command("audit-chains")
def phase9_audit_chains_cmd(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """List Phase 9 pipeline audit chains."""
    paths = ensure_workspace(workspace)
    store = PipelineAuditChainStore(paths["audit_db"])
    store.initialize()
    summaries = store.list_summaries() if hasattr(store, 'list_summaries') else []
    if summaries:
        for s in summaries:
            typer.echo(f"CHAIN {s.chain_id} scenario={s.scenario} status={s.status}")
    else:
        typer.echo("PHASE9 audit-chains none")


@phase9_app.command("replay")
def phase9_replay_cmd(
    replay_config: Path = typer.Option(Path("configs/phase9_replay_fixtures.yaml"), "--config"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    patch_levels_config: Path = typer.Option(Path("configs/patch_levels.yaml"), "--patch-levels-config"),
) -> None:
    """Run Phase 9 replay fixtures."""
    from ai_local.pipeline.replay import run_phase9_replay_fixtures as _run_replay

    paths = ensure_workspace(workspace)
    replay_config = resolve_config(replay_config, "configs/phase9_replay_fixtures.yaml")
    patch_levels_config = resolve_config(patch_levels_config, "configs/patch_levels.yaml")
    results = _run_replay(
        config_path=replay_config,
        workspace_root=paths["base"],
        patch_levels_config=patch_levels_config,
        audit_db=paths["audit_db"],
    )
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        typer.echo(f"REPLAY {status} fixture={r.fixture_id} final_state={r.final_state}")


@phase9_app.command("stress")
def phase9_stress_cmd(
    stress_config: Path = typer.Option(Path("configs/phase9_stress_gates.yaml"), "--config"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Run Phase 9 stress cases."""
    from ai_local.pipeline.stress import run_phase9_stress_cases as _run_stress

    stress_config = resolve_config(stress_config, "configs/phase9_stress_gates.yaml")
    results = _run_stress(
        config_path=stress_config,
        workspace_root=workspace,
    )
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        typer.echo(f"STRESS {status} case={r.case_id} kind={r.kind}")


@phase9_app.command("close")
def phase9_close_cmd(
    replay_config: Path = typer.Option(Path("configs/phase9_replay_fixtures.yaml"), "--replay-config"),
    stress_config: Path = typer.Option(Path("configs/phase9_stress_gates.yaml"), "--stress-config"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    patch_levels_config: Path = typer.Option(Path("configs/patch_levels.yaml"), "--patch-levels-config"),
) -> None:
    """Run full Phase 9 close: replay + stress."""
    paths = ensure_workspace(workspace)
    replay_config = resolve_config(replay_config, "configs/phase9_replay_fixtures.yaml")
    stress_config = resolve_config(stress_config, "configs/phase9_stress_gates.yaml")
    patch_levels_config = resolve_config(patch_levels_config, "configs/patch_levels.yaml")
    result = run_phase9_close(
        replay_config=replay_config,
        stress_config=stress_config,
        workspace_root=paths["base"],
        patch_levels_config=patch_levels_config,
        audit_db=paths["audit_db"],
    )
    status = "PASS" if result.passed else "FAIL"
    typer.echo(f"PHASE9 close {status} replay={result.replay_passed}/{result.replay_total} stress={result.stress_passed}/{result.stress_total}")


# ── Config commands ───────────────────────────────────────────────────────


@config_app.command("show")
def config_show(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    typer.echo(paths["config"].read_text(encoding="utf-8") if paths["config"].exists() else "{}")


@config_app.command("validate")
def config_validate(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    if not paths["config"].exists():
        raise typer.Exit(code=1)
    data = json.loads(paths["config"].read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise typer.Exit(code=1)
    typer.echo("CONFIG OK")


@config_app.command("ollama")
def config_ollama(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    model: str | None = typer.Option(None, "--model", help="Ollama chat model"),
    embedding: str | None = typer.Option(None, "--embedding", help="Ollama embedding model"),
    base_url: str | None = typer.Option(None, "--base-url"),
) -> None:
    """Show or update Ollama configuration for the workspace."""
    ws_config = load_workspace_config(workspace)
    ol_config = ws_config.get("ollama", {})
    if not isinstance(ol_config, dict):
        ol_config = {}
    merged = dict(DEFAULT_OLLAMA_CONFIG)
    merged.update(ol_config)

    changed = False
    if model is not None:
        merged["model"] = model
        merged["enabled"] = True
        changed = True
    if embedding is not None:
        merged["embedding_model"] = embedding
        changed = True
    if base_url is not None:
        merged["base_url"] = base_url
        changed = True

    if changed:
        ws_config["ollama"] = merged
        save_workspace_config(workspace, ws_config)
        typer.echo(f"[Config] Ollama settings updated for {workspace}")

    typer.echo(f"  Chat model: {merged.get('model', '?')}")
    typer.echo(f"  Embedding model: {merged.get('embedding_model', '?')}")
    typer.echo(f"  Base URL: {merged.get('base_url', '?')}")
    typer.echo(f"  Enabled: {merged.get('enabled', False)}")


# ── Index commands ───────────────────────────────────────────────────────


@index_app.command("scan")
def index_scan_group(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    from ai_local.indexer.project import refresh_project_index
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = refresh_project_index(root, store)
    typer.echo(f"INDEX_SCAN indexed={len(batch.documents)} unchanged={len(batch.unchanged_paths)}")


@index_app.command("rebuild")
def index_rebuild_group(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    from ai_local.indexer.project import rebuild_project_index
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = rebuild_project_index(root, store)
    typer.echo(f"INDEX_REBUILD indexed={len(batch.documents)} deleted={len(batch.deleted_paths)}")


@index_app.command("stats")
def index_stats_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    stats = store.stats()
    typer.echo(f"INDEX_STATS files={stats.files} chunks={stats.chunks} symbols={stats.symbols}")


@index_app.command("search")
def index_search_group(
    query: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    hits = store.search_chunks(query, limit=5)
    for hit in hits:
        typer.echo(f"{hit.source_ref} {hit.content[:120].replace(chr(10), ' ')}")


from ai_local.cli.commands.ask import ask_group  # noqa: E402

app.command("ask")(ask_group)


# ── Knowledge commands ───────────────────────────────────────────────────


@knowledge_app.command("add")
def knowledge_add(path: Path, workspace: Path = typer.Option(Path("."), "--workspace", "-w"), tag: str = typer.Option(..., "--tag")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    entry = store.add_file(path, tag)
    typer.echo(f"KNOWLEDGE added id={entry.id} title={entry.title} tags={tag}")


@knowledge_app.command("add-note")
def knowledge_add_note(text: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w"), tag: str = typer.Option(..., "--tag")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    try:
        entry = store.add_note(text, tag)
    except RuntimeError as exc:
        typer.echo(f"KNOWLEDGE note rejected reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc
    typer.echo(f"KNOWLEDGE note added id={entry.id} tags={tag}")


@knowledge_app.command("list")
def knowledge_list(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    entries = store.list_all()
    for entry in entries:
        tags = json.loads(entry.tags_json) if entry.tags_json else []
        typer.echo(f"{entry.id} {entry.kind} {entry.title} tags={','.join(tags)}")


@knowledge_app.command("search")
def knowledge_search(query: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    entries = store.search(query)
    for entry in entries:
        snippet = entry.content[:200].replace('\n', ' ')
        typer.echo(f"{entry.id} {entry.kind} {entry.title} {snippet}")


@knowledge_app.command("remove")
def knowledge_remove(entry_id: int, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    removed = store.remove(entry_id)
    if not removed:
        typer.echo(f"KNOWLEDGE remove missing id={entry_id}")
        raise typer.Exit(code=1)
    typer.echo(f"KNOWLEDGE remove id={entry_id}")


@knowledge_app.command("cleanup")
def knowledge_cleanup(
    dedup: bool = typer.Option(False, "--dedup"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    store.initialize()
    removed = store.cleanup_duplicates() if dedup else []
    typer.echo(f"KNOWLEDGE cleanup removed={len(removed)}")
    if removed:
        typer.echo(f"REMOVED ids={','.join(str(entry_id) for entry_id in removed)}")


@knowledge_app.command("stats")
def knowledge_stats(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.knowledge.sqlite_store import SQLiteKnowledgeStore

    store = SQLiteKnowledgeStore(paths["knowledge_db"])
    stats = store.stats()
    typer.echo(
        "KNOWLEDGE "
        f"total={stats.get('total', 0)} "
        f"notes={stats.get('note', 0)} "
        f"files={stats.get('file', 0)}"
    )


# ── Task commands ────────────────────────────────────────────────────────


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


@task_app.command("approve")
def task_approve_group(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.queue.lifecycle import approve_task

    result = approve_task(tasks_db=paths["tasks_db"], reports_dir=paths["reports"], job_id=task_id)
    typer.echo(f"TASK approve {result.decision} id={task_id} reason=\"{result.reason}\"")
    if result.status is not None:
        typer.echo(f"TASK status={result.status.value}")
    if result.decision == "denied":
        raise typer.Exit(code=1)


@task_app.command("propose")
def task_propose_group(
    task_id: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    ollama: bool = typer.Option(True, "--ollama/--no-ollama", help="Use Ollama to generate code_changes."),
    ollama_model: str | None = typer.Option(None, "--ollama-model"),
    ollama_base_url: str | None = typer.Option(None, "--ollama-base-url"),
) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.llm.ollama import OllamaError
    from ai_local.queue.lifecycle import propose_task, propose_task_deterministic
    from ai_local.runtime.ollama_worker import build_worker_ollama_client

    if not ollama:
        result = propose_task_deterministic(
            workspace=workspace,
            tasks_db=paths["tasks_db"],
            reports_dir=paths["reports"],
            job_id=task_id,
        )
        typer.echo(f"TASK propose {result.decision} id={task_id} reason=\"{result.reason}\"")
        if result.status is not None:
            typer.echo(f"TASK status={result.status.value}")
        if "changes" in result.details:
            typer.echo(f"CHANGES count={result.details['changes']}")
        if result.decision == "denied":
            raise typer.Exit(code=1)
        return

    try:
        client = build_worker_ollama_client(
            workspace=workspace,
            enabled=ollama,
            model=ollama_model,
            base_url=ollama_base_url,
        )
    except OllamaError as exc:
        typer.echo(f"TASK propose denied id={task_id} reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc
    if client is None:
        typer.echo(f"TASK propose denied id={task_id} reason=\"ollama disabled\"")
        raise typer.Exit(code=1)
    result = propose_task(
        workspace=workspace,
        tasks_db=paths["tasks_db"],
        knowledge_db=paths["knowledge_db"],
        reports_dir=paths["reports"],
        job_id=task_id,
        ollama_client=client,
    )
    typer.echo(f"TASK propose {result.decision} id={task_id} reason=\"{result.reason}\"")
    if result.status is not None:
        typer.echo(f"TASK status={result.status.value}")
    if "changes" in result.details:
        typer.echo(f"CHANGES count={result.details['changes']}")
    if result.decision == "denied":
        raise typer.Exit(code=1)


@task_app.command("apply")
def task_apply_group(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.queue.lifecycle import apply_task

    result = apply_task(
        workspace=workspace,
        tasks_db=paths["tasks_db"],
        reports_dir=paths["reports"],
        job_id=task_id,
    )
    typer.echo(f"TASK apply {result.decision} id={task_id} reason=\"{result.reason}\"")
    if result.status is not None:
        typer.echo(f"TASK status={result.status.value}")
    files = result.details.get("files", [])
    if files:
        typer.echo(f"FILES {','.join(str(path) for path in files)}")
    if result.decision == "denied":
        raise typer.Exit(code=1)


@task_app.command("validate")
def task_validate_group(
    task_id: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    command: list[str] | None = typer.Option(None, "--command", "-c"),
    auto: bool = typer.Option(False, "--auto"),
) -> None:
    paths = ensure_workspace(workspace)
    from ai_local.queue.lifecycle import validate_task

    result = validate_task(
        workspace=workspace,
        tasks_db=paths["tasks_db"],
        reports_dir=paths["reports"],
        job_id=task_id,
        commands=command,
        auto=auto,
    )
    typer.echo(f"TASK validate {result.decision} id={task_id} reason=\"{result.reason}\"")
    if result.status is not None:
        typer.echo(f"TASK status={result.status.value}")
    for check in result.details.get("checks", []):
        typer.echo(f"CHECK command=\"{check['command']}\" exit={check['exit_code']}")
    if result.decision == "denied":
        raise typer.Exit(code=1)


# ── Worker commands ──────────────────────────────────────────────────────


@worker_app.command("run")
def worker_run_group(
    once: bool = typer.Option(False, "--once"),
    loop: bool = typer.Option(False, "--loop"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    ollama: bool = typer.Option(False, "--ollama", help="Use Ollama to generate code_change proposals."),
    ollama_model: str | None = typer.Option(None, "--ollama-model"),
    ollama_base_url: str | None = typer.Option(None, "--ollama-base-url"),
) -> None:
    worker_run(
        once=once,
        loop=loop,
        workspace=workspace,
        ollama=ollama,
        ollama_model=ollama_model,
        ollama_base_url=ollama_base_url,
    )


# ── Runtime commands ─────────────────────────────────────────────────────


backup_app = typer.Typer()
runtime_app.add_typer(backup_app, name="backup")


@backup_app.command("create")
def runtime_backup_create_group(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    runtime_backup_create(workspace=workspace)


@backup_app.command("restore")
def runtime_backup_restore_group(backup_path: Path, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    result = restore_runtime_backup(backup_dir=backup_path, tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo(f"{result.decision} {result.reason}")


# ── Gate commands ────────────────────────────────────────────────────────


@gate_app.command("run")
def gate_run_group(level: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    typer.echo(f"GATE run level={level} workspace={workspace}")


@gate_app.command("promote")
def gate_promote_group(
    max_level: str | None = typer.Option(None),
    gates_config: Path = typer.Option(Path("configs/gates.yaml")),
    tools_config: Path = typer.Option(Path("configs/tools.yaml")),
    cwd: Path = typer.Option(Path(".")),
) -> None:
    """Promote gates up to max_level."""
    from ai_local.harness.test_gate import run_promoted_gates

    gates_config = resolve_config(gates_config, "configs/gates.yaml")
    tools_config = resolve_config(tools_config, "configs/tools.yaml")
    level_results = run_promoted_gates(
        gates_config_path=gates_config,
        tools_config_path=tools_config,
        cwd=cwd,
        max_level=max_level,
    )
    failed = False
    for level_result in level_results:
        typer.echo(f"[{level_result.level}]")
        for result in level_result.results:
            status = "PASS" if result.passed else "FAIL"
            typer.echo(f"{status} {result.command_id} exit={result.exit_code}")
            if not result.passed:
                failed = True
                if result.stderr:
                    typer.echo(result.stderr)
        if not level_result.passed:
            typer.echo(f"STOP promotion at {level_result.level}")
            break
    if failed:
        raise typer.Exit(code=1)


@gate_app.command("project-retrieval")
def gate_project_retrieval_group(
    query: str = typer.Argument(...),
    root: Path = typer.Option(None, "--root", "-r", help="Project root directory"),
    knowledge_db: Path = typer.Option(None, "--knowledge-db", help="Knowledge db path"),
    chunk_lines: int = typer.Option(40, min=1),
    max_hits: int = typer.Option(5, min=1),
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
) -> None:
    """Query project retrieval.

    Provide --workspace (resolves root + db from workspace config)
    or --root (optionally --knowledge-db) explicitly.
    """
    from ai_local.indexer.project import refresh_and_retrieve_project
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore
    from ai_local.config.workspace import ensure_workspace, load_workspace_config

    if workspace is not None:
        ws_config = load_workspace_config(workspace)
        resolved_root = root if root is not None else workspace
        resolved_kb = knowledge_db if knowledge_db is not None else (
            Path(ws_config.get("knowledge_db", str(ensure_workspace(workspace)["knowledge_db"])))
        )
    else:
        resolved_root = root if root is not None else Path(".")
        resolved_kb = knowledge_db if knowledge_db is not None else Path("knowledge.db")

    result = refresh_and_retrieve_project(
        query,
        resolved_root,
        KnowledgeIndexStore(resolved_kb),
        chunk_lines=chunk_lines,
        max_hits=max_hits,
    )
    typer.echo(
        f"INDEX indexed={len(result.batch.documents)} "
        f"unchanged={len(result.batch.unchanged_paths)} "
        f"skipped={len(result.batch.skipped_paths)}"
    )
    typer.echo(
        f"RETRIEVE decision={result.package.decision} "
        f"hits={len(result.package.selected_hits)}"
    )
    for ref in result.package.evidence_refs:
        typer.echo(f"EVIDENCE {ref}")


@gate_app.command("patch-levels")
def gate_patch_levels_group(
    config: Path = typer.Option(Path("configs/patch_levels.yaml")),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Validate patch levels configuration."""
    from ai_local.harness.patch_levels import load_patch_levels, validate_patch_levels

    config = resolve_config(config, "configs/patch_levels.yaml")
    levels = load_patch_levels(config)
    errors = validate_patch_levels(levels)
    if errors:
        for error in errors:
            typer.echo(f"FAIL {error}")
        raise typer.Exit(code=1)
    for level in levels:
        typer.echo(
            f"PASS {level.name} files={level.max_files_changed} "
            f"lines={level.max_changed_lines} hop={level.max_hop_depth} "
            f"risk={level.risk_ceiling}"
        )


@gate_app.command("memory-regression")
def gate_memory_regression_group(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_regression_gates.yaml")),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Run memory regression gate promotion."""
    from ai_local.harness.memory_regression_gate import run_memory_regression_promotion

    config = resolve_config(config, "configs/memory_regression_gates.yaml")
    results = run_memory_regression_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_state_hops={result.max_state_hops} "
            f"checks={len(result.checked_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


# ── Global Developer / Sprint commands (flat) ────────────────────────────


@app.command("global-developer")
def global_developer_cmd(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    config: Path = typer.Option(Path("configs/global_developer_harness.yaml"), "--config"),
) -> None:
    """Run global developer harness validation."""
    from ai_local.harness.global_developer_harness import (
        GlobalDeveloperHarnessResult,
        load_developer_phase_coverage,
    )

    paths = ensure_workspace(workspace)
    config = resolve_config(config, "configs/global_developer_harness.yaml")
    coverage = load_developer_phase_coverage(config)
    typer.echo(f"GLOBAL funcs={len(coverage.functional_requirements)} nonfuncs={len(coverage.non_functional_requirements)} gates={len(coverage.known_gate_harnesses)}")


@app.command("developer-sprints")
def developer_sprints_cmd(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    config: Path = typer.Option(Path("configs/developer_sprints.yaml"), "--config"),
) -> None:
    """Run developer sprint plan validation."""
    from ai_local.harness.developer_sprint_harness import (
        DeveloperSprintHarnessResult,
        load_developer_sprint_plan,
    )

    paths = ensure_workspace(workspace)
    config = resolve_config(config, "configs/developer_sprints.yaml")
    plan = load_developer_sprint_plan(config)
    typer.echo(f"SPRINTS count={len(plan.sprints)}")


# ── Service submit-task (works with running pywin32 service) ─────────────


@service_app.command("submit-task")
def service_submit_task_cmd(
    task: str = typer.Argument(..., help="Task description"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    wait: float = typer.Option(0.0, "--wait", help="Seconds to wait for processing"),
    strategy: str = typer.Option("pywin32", "--strategy"),
) -> None:
    """Submit a task via the running service, optionally wait for processing."""
    from ai_local.queue.models import Job
    from ai_local.queue.store import SQLiteQueueStore
    from time import sleep

    paths = ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])
    job_id = f"task-{len(queue.list_jobs())+1}"
    queue.enqueue(Job(id=job_id, type="demo", payload={"task": task}))
    typer.echo(f"SERVICE task submitted id={job_id}")

    if wait > 0:
        for _ in range(int(wait * 2)):
            job = queue.get(job_id)
            if job is None or job.status.value != "pending":
                status = job.status.value if job else "unknown"
                typer.echo(f"SERVICE task status={status}")
                return
            sleep(0.5)
        typer.echo(f"SERVICE task still pending after {wait}s")


@service_app.command("tail")
def service_tail_cmd(
    lines: int = typer.Option(30, "--lines", "-n"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    strategy: str = typer.Option("pywin32", "--strategy"),
) -> None:
    """Tail daemon/service log lines from the running service."""
    paths = ensure_workspace(workspace)
    log_candidates = [
        ("daemon.log", paths["logs"] / "daemon.log"),
        ("service.stdout.log", paths["logs"] / "service.stdout.log"),
        ("service.stderr.log", paths["logs"] / "service.stderr.log"),
    ]
    found = False
    for name, log_path in log_candidates:
        if log_path.exists():
            if not found:
                found = True
            content = log_path.read_text(encoding="utf-8").strip().splitlines()
            tail = content[-lines:] if lines > 0 else content
            typer.echo(f"TAIL {name} count={len(tail)}")
            for line in tail:
                typer.echo(line)
    if not found:
        typer.echo(f"TAIL none path={paths['logs']}")


# ── Top-level commands ───────────────────────────────────────────────────


@app.command()
def init(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    ollama_enabled: bool = typer.Option(False, "--ollama-enabled"),
) -> None:
    paths = ensure_workspace(workspace)
    config = {
        "workspace": str(workspace.resolve()),
        "knowledge_db": str(paths["knowledge_db"]),
        "runtime_db": str(paths["runtime_db"]),
        "tasks_db": str(paths["tasks_db"]),
        "audit_db": str(paths["audit_db"]),
    }
    if ollama_enabled:
        ol_config = dict(DEFAULT_OLLAMA_CONFIG)
        ol_config["enabled"] = True
        config["ollama"] = ol_config
    save_workspace_config(workspace, config)
    typer.echo(f"INIT workspace={workspace} dir={paths['base']}")


@app.command("index-scan")
def index_scan(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    from ai_local.indexer.project import refresh_project_index
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = refresh_project_index(root, store)
    typer.echo(f"INDEX_SCAN indexed={len(batch.documents)} unchanged={len(batch.unchanged_paths)}")


@app.command("index-rebuild")
def index_rebuild(
    root: Path = typer.Option(Path("."), "--root", "-r"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    from ai_local.indexer.project import rebuild_project_index
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    batch = rebuild_project_index(root, store)
    typer.echo(f"INDEX_REBUILD indexed={len(batch.documents)} deleted={len(batch.deleted_paths)}")


@app.command("index-stats")
def index_stats(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    stats = store.stats()
    typer.echo(f"INDEX_STATS files={stats.files} chunks={stats.chunks} symbols={stats.symbols}")


@app.command("index-search")
def index_search(
    query: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    from ai_local.indexer.sqlite_store import KnowledgeIndexStore

    paths = ensure_workspace(workspace)
    store = KnowledgeIndexStore(paths["knowledge_db"])
    store.initialize()
    hits = store.search_chunks(query, limit=5)
    for hit in hits:
        typer.echo(f"{hit.source_ref} {hit.content[:120].replace(chr(10), ' ')}")


@app.command("runtime-backup-create")
def runtime_backup_create(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    result = create_runtime_backup(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], backup_dir=paths["backups"])
    typer.echo(f"{result.decision} {result.reason}")


@app.command("runtime-backup-restore")
def runtime_backup_restore(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    result = restore_runtime_backup(backup_dir=paths["backups"], tasks_db=paths["tasks_db"], audit_db=paths["audit_db"])
    typer.echo(f"{result.decision} {result.reason}")


@app.command("task-submit")
def task_submit(
    task: str,
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    paths = ensure_workspace(workspace)
    queue = SQLiteQueueStore(paths["tasks_db"])
    queue.enqueue(Job(id=f"task-{len(queue.list_jobs())+1}", type="demo", payload={"task": task}))
    typer.echo("TASK submitted")


@app.command("task-list")
def task_list(workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    for job in SQLiteQueueStore(paths["tasks_db"]).list_jobs():
        typer.echo(f"{job.id} {job.status.value} {job.type}")


@app.command("task-read")
def task_read(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    job = SQLiteQueueStore(paths["tasks_db"]).get(task_id)
    if job is None:
        raise typer.Exit(code=1)
    typer.echo(json.dumps(job.model_dump(mode="json"), indent=2))


@app.command("task-cancel")
def task_cancel(task_id: str, workspace: Path = typer.Option(Path("."), "--workspace", "-w")) -> None:
    paths = ensure_workspace(workspace)
    result = cancel_queue_job(tasks_db=paths["tasks_db"], audit_db=paths["audit_db"], job_id=task_id)
    typer.echo(result.decision)


def worker_run(
    once: bool = typer.Option(False, "--once"),
    loop: bool = typer.Option(False, "--loop"),
    workspace: Path = typer.Option(Path('.'), "--workspace", "-w"),
    ollama: bool = typer.Option(False, "--ollama"),
    ollama_model: str | None = typer.Option(None, "--ollama-model"),
    ollama_base_url: str | None = typer.Option(None, "--ollama-base-url"),
) -> None:
    """Run the worker."""
    ollama_client = _build_worker_ollama_client(
        workspace=workspace,
        enabled=ollama,
        model=ollama_model,
        base_url=ollama_base_url,
    )
    if once:
        result = run_worker_once(workspace, ollama_client=ollama_client)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        raise typer.Exit(code=0)

    while True:
        result = run_worker_once(workspace, ollama_client=ollama_client)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        if not loop:
            break
    raise typer.Exit(code=0)


def _build_worker_ollama_client(
    *,
    workspace: Path,
    enabled: bool,
    model: str | None,
    base_url: str | None,
):
    if not enabled:
        return None
    from ai_local.llm.ollama import OllamaClient, OllamaConfig, OllamaError

    config_data = get_ollama_config(workspace)
    resolved_model = model or str(config_data.get("model", "qwen2.5:0.5b"))
    resolved_base_url = base_url or str(config_data.get("base_url", "http://127.0.0.1:11434"))
    client = OllamaClient(OllamaConfig(base_url=resolved_base_url, model=resolved_model))
    try:
        if not client.health_check():
            raise OllamaError(f"Ollama unreachable at {resolved_base_url}")
        client.ensure_model()
    except OllamaError as exc:
        typer.echo(f"WORKER ollama FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc
    typer.echo(f"WORKER ollama model={client.model}")
    return client
