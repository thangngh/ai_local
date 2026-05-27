import json
from pathlib import Path

import typer

from ai_local.harness.test_gate import run_patch_gate, run_promoted_gates
from ai_local.harness.noise_gate import run_noise_promotion
from ai_local.harness.memory_regression_gate import run_memory_regression_promotion
from ai_local.harness.memory_layer_gate import run_memory_layer_promotion
from ai_local.harness.composite_gate import run_composite_promotion
from ai_local.harness.decision_gate import run_decision_promotion
from ai_local.harness.retrieval_gate import run_retrieval_promotion
from ai_local.harness.agent_loop_gate import run_agent_loop_promotion
from ai_local.harness.big_harness import load_big_harness_policy, validate_big_harness_policy
from ai_local.harness.small_patch_harness import run_small_patch_policy_check
from ai_local.harness.patch_pipeline_harness import run_patch_pipeline_promotion
from ai_local.harness.patch_levels import load_patch_levels, validate_patch_levels
from ai_local.harness.evaluation_gate import run_evaluation_promotion
from ai_local.harness.confirmation_gate import run_confirmation_promotion
from ai_local.harness.knowledge_gate import run_knowledge_promotion
from ai_local.harness.evidence_rank_gate import run_evidence_rank_promotion
from ai_local.harness.tool_combo_gate import run_tool_combo_promotion
from ai_local.harness.skill_gate import run_skill_promotion
from ai_local.harness.memory_sql_gate import run_memory_sql_promotion
from ai_local.harness.conflict_path_gate import run_conflict_path_promotion
from ai_local.harness.multi_instance_conflict_gate import (
    run_multi_instance_conflict_promotion,
)
from ai_local.harness.request_lifecycle_gate import run_request_lifecycle_promotion
from ai_local.harness.prompt_injection_refusal_gate import (
    run_prompt_injection_refusal_promotion,
)
from ai_local.harness.thread_control_gate import run_thread_control_promotion
from ai_local.harness.operational_safety_gate import run_operational_safety_promotion
from ai_local.harness.memory_governance_gate import run_memory_governance_promotion
from ai_local.harness.flow_memory_rating_gate import run_flow_memory_rating_promotion
from ai_local.harness.global_developer_harness import run_global_developer_harness
from ai_local.harness.developer_sprint_harness import run_developer_sprint_harness
from ai_local.doctor import run_doctor
from ai_local.benchmark.history import load_benchmark_history, render_trend_table
from ai_local.benchmark.ollama_eval import OllamaBenchmarkConfig, load_ollama_prompt_config
from ai_local.benchmark.replay import load_benchmark_report, render_replay_report
from ai_local.benchmark.runner import (
    load_ollama_benchmark_config,
    run_golden_benchmark,
    write_benchmark_report,
)
from ai_local.benchmark.summary import render_summary_table
from ai_local.benchmark.thresholds import enforce_thresholds, load_benchmark_thresholds
from ai_local.llm.ollama import OllamaClient, OllamaConfig, OllamaError
from ai_local.harness.phase_fast_gate import run_phase_fast_gates, write_phase_fast_gate_report
from ai_local.indexer.project import (
    rebuild_project_index,
    refresh_and_retrieve_project,
    refresh_project_index,
)
from ai_local.indexer.sqlite_store import KnowledgeIndexStore
from ai_local.agent.operations import (
    cancel_agent_run,
    list_agent_runs,
    stop_agent_run,
)
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore
from ai_local.pipeline.audit_chain import PipelineAuditChainStore
from ai_local.pipeline.phase9_close import run_phase9_close
from ai_local.pipeline.report import Phase9ReportScenario, run_phase9_integration_report
from ai_local.pipeline.replay import run_phase9_replay_fixtures
from ai_local.pipeline.stress import run_phase9_stress_cases
from ai_local.queue.store import SQLiteQueueStore
from ai_local.queue.operations import (
    cancel_queue_job,
    list_queue_jobs,
    retry_dead_letter_job,
)
from ai_local.runtime.control_plane import (
    build_runtime_control_snapshot,
    render_runtime_control_snapshot,
)
from ai_local.runtime.tui import run_runtime_tui_frames
from ai_local.runtime.backup import create_runtime_backup, restore_runtime_backup
from ai_local.skills.store import (
    InstalledSkillStore,
    cleanup_stale_installed_skills,
    rebuild_installed_skill_registry,
    refresh_installed_skill_registry,
)
from ai_local.tools.sandbox import (
    SandboxPolicy,
    SandboxRunRequest,
    SubprocessSandboxAdapter,
)

app = typer.Typer()


@app.command()
def gate(
    commands: list[str] = typer.Argument(...),
    config: Path = typer.Option(Path("configs/tools.yaml")),
    cwd: Path = typer.Option(Path(".")),
) -> None:
    if commands and commands[0] == "gate":
        commands = commands[1:]
    results = run_patch_gate(commands, config_path=config, cwd=cwd)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.command_id} exit={result.exit_code}")
        if not result.passed:
            failed = True
            if result.stderr:
                typer.echo(result.stderr)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def promote(
    max_level: str | None = typer.Option(None),
    gates_config: Path = typer.Option(Path("configs/gates.yaml")),
    tools_config: Path = typer.Option(Path("configs/tools.yaml")),
    cwd: Path = typer.Option(Path(".")),
) -> None:
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


@app.command()
def noise(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/noise_gates.yaml")),
) -> None:
    results = run_noise_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"checks={len(result.checked_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def memory_regression(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_regression_gates.yaml")),
) -> None:
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


@app.command()
def memory_layers(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_layer_gates.yaml")),
) -> None:
    results = run_memory_layer_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"layers={len(result.checked_layers)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def composite(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/composite_gates.yaml")),
) -> None:
    results = run_composite_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"gates={len(result.checked_gate_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def decision(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/decision_gates.yaml")),
) -> None:
    results = run_decision_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def retrieval(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/retrieval_gates.yaml")),
) -> None:
    results = run_retrieval_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def project_retrieval(
    query: str = typer.Argument(...),
    root: Path = typer.Option(Path(".")),
    knowledge_db: Path = typer.Option(Path("knowledge.db")),
    chunk_lines: int = typer.Option(40, min=1),
    max_hits: int = typer.Option(5, min=1),
) -> None:
    result = refresh_and_retrieve_project(
        query,
        root,
        KnowledgeIndexStore(knowledge_db),
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


@app.command()
def project_index(
    root: Path = typer.Option(Path(".")),
    knowledge_db: Path = typer.Option(Path("knowledge.db")),
    chunk_lines: int = typer.Option(40, min=1),
) -> None:
    batch = refresh_project_index(root, KnowledgeIndexStore(knowledge_db), chunk_lines=chunk_lines)
    typer.echo(
        f"INDEX indexed={len(batch.documents)} unchanged={len(batch.unchanged_paths)} "
        f"deleted={len(batch.deleted_paths)} skipped={len(batch.skipped_paths)}"
    )


@app.command()
def project_index_stats(knowledge_db: Path = typer.Option(Path("knowledge.db"))) -> None:
    store = KnowledgeIndexStore(knowledge_db)
    store.initialize()
    stats = store.stats()
    typer.echo(f"INDEX_STATS files={stats.files} chunks={stats.chunks} symbols={stats.symbols}")


@app.command()
def project_index_rebuild(
    root: Path = typer.Option(Path(".")),
    knowledge_db: Path = typer.Option(Path("knowledge.db")),
    chunk_lines: int = typer.Option(40, min=1),
) -> None:
    batch = rebuild_project_index(root, KnowledgeIndexStore(knowledge_db), chunk_lines=chunk_lines)
    typer.echo(
        f"REBUILD indexed={len(batch.documents)} deleted={len(batch.deleted_paths)} "
        f"skipped={len(batch.skipped_paths)}"
    )


@app.command()
def skill_registry_refresh(
    root: Path = typer.Option(Path(".codex/skills")),
    metadata_db: Path = typer.Option(Path("metadata.db")),
    audit_ref: str | None = typer.Option(None),
) -> None:
    result = refresh_installed_skill_registry(
        root,
        InstalledSkillStore(metadata_db),
        audit_ref=audit_ref,
    )
    typer.echo(
        f"SKILL_REGISTRY_REFRESH upserted={len(result.upserted)} "
        f"unchanged={len(result.unchanged)} deleted={len(result.deleted)} "
        f"skipped={len(result.skipped)}"
    )


@app.command()
def skill_registry_cleanup(
    root: Path = typer.Option(Path(".codex/skills")),
    metadata_db: Path = typer.Option(Path("metadata.db")),
) -> None:
    deleted = cleanup_stale_installed_skills(root, InstalledSkillStore(metadata_db))
    typer.echo(f"SKILL_REGISTRY_CLEANUP deleted={len(deleted)}")


@app.command()
def skill_registry_rebuild(
    root: Path = typer.Option(Path(".codex/skills")),
    metadata_db: Path = typer.Option(Path("metadata.db")),
    audit_ref: str | None = typer.Option(None),
) -> None:
    result = rebuild_installed_skill_registry(
        root,
        InstalledSkillStore(metadata_db),
        audit_ref=audit_ref,
    )
    typer.echo(
        f"SKILL_REGISTRY_REBUILD upserted={len(result.upserted)} "
        f"deleted={len(result.deleted)} skipped={len(result.skipped)}"
    )


@app.command()
def skill_registry_stats(
    root: Path = typer.Option(Path(".codex/skills")),
    metadata_db: Path = typer.Option(Path("metadata.db")),
) -> None:
    store = InstalledSkillStore(metadata_db)
    store.initialize()
    stats = store.stats(root=root)
    typer.echo(
        f"SKILL_REGISTRY_STATS packages={stats.packages} "
        f"trusted={stats.trusted} stale={stats.stale}"
    )


@app.command()
def agent_loop(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/agent_loop_gates.yaml")),
) -> None:
    results = run_agent_loop_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def big_harness(config: Path = typer.Option(Path("configs/big_harness.yaml"))) -> None:
    policy = load_big_harness_policy(config)
    errors = validate_big_harness_policy(policy)
    if errors:
        for error in errors:
            typer.echo(f"FAIL {error}")
        raise typer.Exit(code=1)
    typer.echo(
        "PASS big_harness "
        f"max_steps={policy.max_steps} max_tool_calls={policy.max_tool_calls} "
        f"max_hop_depth={policy.max_hop_depth}"
    )


@app.command()
def small_patch(config: Path = typer.Option(Path("configs/small_patch_harness.yaml"))) -> None:
    results = run_small_patch_policy_check(config)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(f"{status} {result.level}")
        if not result.passed:
            failed = True
            typer.echo(result.reason)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def patch_pipeline(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/patch_pipeline_harness.yaml")),
) -> None:
    results = run_patch_pipeline_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def patch_levels(config: Path = typer.Option(Path("configs/patch_levels.yaml"))) -> None:
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


@app.command()
def evaluation(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/evaluation_gates.yaml")),
) -> None:
    results = run_evaluation_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def confirmation(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/confirmation_gates.yaml")),
) -> None:
    results = run_confirmation_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def knowledge(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/knowledge_gates.yaml")),
) -> None:
    results = run_knowledge_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def evidence_rank(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/evidence_rank_gates.yaml")),
) -> None:
    results = run_evidence_rank_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def tool_combo(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/tool_combo_gates.yaml")),
) -> None:
    results = run_tool_combo_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def skills(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/skill_gates.yaml")),
    root: Path = typer.Option(Path(".")),
) -> None:
    results = run_skill_promotion(config_path=config, root=root, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def memory_sql(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_sql_gates.yaml")),
) -> None:
    results = run_memory_sql_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def conflict_paths(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/conflict_path_gates.yaml")),
) -> None:
    results = run_conflict_path_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def multi_conflict(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/multi_instance_conflict_gates.yaml")),
) -> None:
    results = run_multi_instance_conflict_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def request_lifecycle(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/request_lifecycle_gates.yaml")),
) -> None:
    results = run_request_lifecycle_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def prompt_injection(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/prompt_injection_refusal_gates.yaml")),
) -> None:
    results = run_prompt_injection_refusal_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def thread_control(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/thread_control_gates.yaml")),
) -> None:
    results = run_thread_control_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def operational_safety(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/operational_safety_gates.yaml")),
) -> None:
    results = run_operational_safety_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def memory_governance(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/memory_governance_gates.yaml")),
) -> None:
    results = run_memory_governance_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def flow_memory_rating(
    max_level: str | None = typer.Option(None),
    config: Path = typer.Option(Path("configs/flow_memory_rating_gates.yaml")),
) -> None:
    results = run_flow_memory_rating_promotion(config_path=config, max_level=max_level)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{status} {result.level} max_hop_depth={result.max_hop_depth} "
            f"cases={len(result.checked_case_ids)}"
        )
        if not result.passed:
            failed = True
            typer.echo(result.reason)
            break
    if failed:
        raise typer.Exit(code=1)


@app.command()
def global_developer(
    config: Path = typer.Option(Path("configs/global_developer_harness.yaml")),
    root: Path = typer.Option(Path(".")),
) -> None:
    result = run_global_developer_harness(config_path=config, root=root)
    status = "PASS" if result.passed else "FAIL"
    typer.echo(
        f"{status} global_developer functional={result.functional_count} "
        f"non_functional={result.non_functional_count} gates={result.gate_count}"
    )
    if result.errors:
        for error in result.errors:
            typer.echo(error)
        raise typer.Exit(code=1)


@app.command()
def developer_sprints(
    config: Path = typer.Option(Path("configs/developer_sprints.yaml")),
    root: Path = typer.Option(Path(".")),
) -> None:
    result = run_developer_sprint_harness(config_path=config, root=root)
    status = "PASS" if result.passed else "FAIL"
    typer.echo(
        f"{status} developer_sprints sprints={result.sprint_count} "
        f"functionals={result.functional_count}"
    )
    if result.errors:
        for error in result.errors:
            typer.echo(error)
        raise typer.Exit(code=1)


@app.command()
def phase9_integration_report(
    scenario: Phase9ReportScenario = typer.Option("ready"),
    workspace_root: Path = typer.Option(Path(".")),
    patch_levels_config: Path = typer.Option(Path("configs/patch_levels.yaml")),
    audit_db: Path | None = typer.Option(None),
    output: Path | None = typer.Option(None),
) -> None:
    report = run_phase9_integration_report(
        scenario=scenario,
        workspace_root=workspace_root,
        patch_levels_config=patch_levels_config,
        audit_db=audit_db,
    )
    payload = json.dumps(report, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    typer.echo(payload)


@app.command()
def phase9_audit_chains(
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    summaries = PipelineAuditChainStore(audit_db).list_summaries()
    for summary in summaries:
        typer.echo(
            f"CHAIN {summary.chain_id} scenario={summary.scenario} "
            f"status={summary.status} final_state={summary.final_state} "
            f"evidence={summary.evidence_count} audit_events={summary.audit_event_count}"
        )


@app.command()
def phase9_replay(
    config: Path = typer.Option(Path("configs/phase9_replay_fixtures.yaml")),
    workspace_root: Path = typer.Option(Path(".")),
    patch_levels_config: Path = typer.Option(Path("configs/patch_levels.yaml")),
    audit_db: Path | None = typer.Option(None),
) -> None:
    results = run_phase9_replay_fixtures(
        config_path=config,
        workspace_root=workspace_root,
        patch_levels_config=patch_levels_config,
        audit_db=audit_db,
    )
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        chain = f" chain={result.chain_id}" if result.chain_id is not None else ""
        typer.echo(
            f"{status} {result.fixture_id} scenario={result.scenario} "
            f"status={result.status} final_state={result.final_state}{chain}"
        )
        if result.reasons:
            failed = True
            for reason in result.reasons:
                typer.echo(reason)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def phase9_stress(
    config: Path = typer.Option(Path("configs/phase9_stress_gates.yaml")),
    workspace_root: Path = typer.Option(Path(".phase9-stress")),
) -> None:
    results = run_phase9_stress_cases(config_path=config, workspace_root=workspace_root)
    failed = False
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        metrics = " ".join(f"{key}={value}" for key, value in sorted(result.metrics.items()))
        typer.echo(
            f"{status} {result.case_id} kind={result.kind} "
            f"hop_depth={result.hop_depth} {metrics}"
        )
        if result.reasons:
            failed = True
            for reason in result.reasons:
                typer.echo(reason)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def phase9_close(
    replay_config: Path = typer.Option(Path("configs/phase9_replay_fixtures.yaml")),
    stress_config: Path = typer.Option(Path("configs/phase9_stress_gates.yaml")),
    workspace_root: Path = typer.Option(Path(".phase9-close")),
    patch_levels_config: Path = typer.Option(Path("configs/patch_levels.yaml")),
    audit_db: Path | None = typer.Option(None),
) -> None:
    result = run_phase9_close(
        replay_config=replay_config,
        stress_config=stress_config,
        workspace_root=workspace_root,
        patch_levels_config=patch_levels_config,
        audit_db=audit_db,
    )
    status = "PASS" if result.passed else "FAIL"
    typer.echo(
        f"{status} phase9_close replay={result.replay_passed}/{result.replay_total} "
        f"stress={result.stress_passed}/{result.stress_total}"
    )
    if result.reasons:
        for reason in result.reasons:
            typer.echo(reason)
        raise typer.Exit(code=1)


@app.command()
def runtime_store_stats(
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    queue_counts = SQLiteQueueStore(tasks_db).status_counts()
    run_counts = SQLiteAgentRunStore(tasks_db).status_counts()
    audit_count = SQLiteAuditStore(audit_db).count()
    typer.echo(f"RUNTIME_AUDIT events={audit_count}")
    typer.echo(
        "RUNTIME_QUEUE "
        + " ".join(f"{status}={count}" for status, count in sorted(queue_counts.items()))
    )
    typer.echo(
        "RUNTIME_AGENT_RUNS "
        + " ".join(f"{status}={count}" for status, count in sorted(run_counts.items()))
    )


@app.command()
def runtime_schema_versions(
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    task_versions = {
        **SQLiteQueueStore(tasks_db).schema_versions(),
        **SQLiteAgentRunStore(tasks_db).schema_versions(),
    }
    audit_versions = SQLiteAuditStore(audit_db).schema_versions()
    for component, version in sorted({**task_versions, **audit_versions}.items()):
        typer.echo(f"SCHEMA_VERSION component={component} version={version}")


@app.command()
def tool_sandbox_check(
    command: list[str] = typer.Argument(...),
    cwd: Path = typer.Option(Path(".")),
    workspace_root: Path = typer.Option(Path(".")),
    timeout_seconds: int = typer.Option(5, min=1),
    max_timeout_seconds: int = typer.Option(30, min=1),
    allow_executable: list[str] | None = typer.Option(None),
) -> None:
    allowed = frozenset(allow_executable or ([command[0], Path(command[0]).name] if command else []))
    result = SubprocessSandboxAdapter().run(
        SandboxRunRequest(
            command=command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            policy=SandboxPolicy(
                workspace_root=workspace_root,
                max_timeout_seconds=max_timeout_seconds,
                allowed_executables=allowed,
            ),
        )
    )
    typer.echo(
        f"SANDBOX decision={result.decision} backend={result.backend} "
        f"timeout={result.timeout_seconds} reason={result.reason}"
    )
    if result.decision == "denied":
        raise typer.Exit(code=1)


@app.command()
def runtime_control_panel(
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
    recent_audit_limit: int = typer.Option(5, min=0),
    fail_on_critical: bool = typer.Option(False),
) -> None:
    snapshot = build_runtime_control_snapshot(
        tasks_db=tasks_db,
        audit_db=audit_db,
        recent_audit_limit=recent_audit_limit,
    )
    typer.echo(render_runtime_control_snapshot(snapshot))
    if fail_on_critical and snapshot.health == "critical":
        raise typer.Exit(code=1)


@app.command()
def runtime_tui(
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
    iterations: int = typer.Option(1, min=1),
    refresh_seconds: float = typer.Option(0, min=0),
    recent_audit_limit: int = typer.Option(5, min=0),
    fail_on_critical: bool = typer.Option(False),
) -> None:
    frames = run_runtime_tui_frames(
        tasks_db=tasks_db,
        audit_db=audit_db,
        iterations=iterations,
        refresh_seconds=refresh_seconds,
        recent_audit_limit=recent_audit_limit,
    )
    for index, frame in enumerate(frames):
        if index:
            typer.echo("")
        typer.echo(frame.text)
    if fail_on_critical and any(frame.health == "critical" for frame in frames):
        raise typer.Exit(code=1)


@app.command()
def queue_jobs(
    tasks_db: Path = typer.Option(Path("tasks.db")),
) -> None:
    jobs = list_queue_jobs(tasks_db=tasks_db)
    for job in jobs:
        typer.echo(
            f"QUEUE_JOB id={job.id} type={job.type} status={job.status.value} "
            f"priority={job.priority} attempts={job.attempts}/{job.max_attempts} "
            f"last_error={job.last_error or ''}"
        )


@app.command()
def queue_retry(
    job_id: str = typer.Argument(...),
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    result = retry_dead_letter_job(tasks_db=tasks_db, audit_db=audit_db, job_id=job_id)
    status = "PASS" if result.decision == "succeeded" else "DENY"
    job_status = f" status={result.job.status.value}" if result.job is not None else ""
    typer.echo(f"{status} queue_retry id={job_id}{job_status} reason={result.reason}")
    if result.decision != "succeeded":
        raise typer.Exit(code=1)


@app.command()
def queue_cancel(
    job_id: str = typer.Argument(...),
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    result = cancel_queue_job(tasks_db=tasks_db, audit_db=audit_db, job_id=job_id)
    status = "PASS" if result.decision == "succeeded" else "DENY"
    job_status = f" status={result.job.status.value}" if result.job is not None else ""
    typer.echo(f"{status} queue_cancel id={job_id}{job_status} reason={result.reason}")
    if result.decision != "succeeded":
        raise typer.Exit(code=1)


@app.command()
def agent_runs(
    tasks_db: Path = typer.Option(Path("tasks.db")),
) -> None:
    runs = list_agent_runs(tasks_db=tasks_db)
    for run in runs:
        typer.echo(
            f"AGENT_RUN id={run.id} status={run.status.value} "
            f"decision={run.decision or ''} next_state={run.next_state or ''} "
            f"goal={run.goal}"
        )


@app.command()
def agent_run_stop(
    run_id: str = typer.Argument(...),
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    result = stop_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id=run_id)
    status = "PASS" if result.decision == "succeeded" else "DENY"
    run_status = f" status={result.run.status.value}" if result.run is not None else ""
    typer.echo(f"{status} agent_run_stop id={run_id}{run_status} reason={result.reason}")
    if result.decision != "succeeded":
        raise typer.Exit(code=1)


@app.command()
def agent_run_cancel(
    run_id: str = typer.Argument(...),
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    result = cancel_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id=run_id)
    status = "PASS" if result.decision == "succeeded" else "DENY"
    run_status = f" status={result.run.status.value}" if result.run is not None else ""
    typer.echo(f"{status} agent_run_cancel id={run_id}{run_status} reason={result.reason}")
    if result.decision != "succeeded":
        raise typer.Exit(code=1)


@app.command()
def runtime_backup(
    backup_dir: Path = typer.Argument(...),
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    result = create_runtime_backup(tasks_db=tasks_db, audit_db=audit_db, backup_dir=backup_dir)
    status = "PASS" if result.decision == "succeeded" else "DENY"
    manifest = f" manifest={result.manifest_path}" if result.manifest_path is not None else ""
    typer.echo(f"{status} runtime_backup dir={result.backup_dir}{manifest} reason={result.reason}")
    if result.decision != "succeeded":
        raise typer.Exit(code=1)


@app.command()
def runtime_restore(
    backup_dir: Path = typer.Argument(...),
    tasks_db: Path = typer.Option(Path("tasks.db")),
    audit_db: Path = typer.Option(Path("audit.db")),
) -> None:
    result = restore_runtime_backup(backup_dir=backup_dir, tasks_db=tasks_db, audit_db=audit_db)
    status = "PASS" if result.decision == "succeeded" else "DENY"
    manifest = f" manifest={result.manifest_path}" if result.manifest_path is not None else ""
    typer.echo(f"{status} runtime_restore dir={result.backup_dir}{manifest} reason={result.reason}")
    if result.decision != "succeeded":
        raise typer.Exit(code=1)


@app.command("benchmark-run")
def benchmark_run(
    tasks_root: Path = typer.Option(Path("golden_tasks")),
    benchmark_id: str = typer.Option("local_ai_bench"),
    run_id: str | None = typer.Option(None),
    output: Path = typer.Option(Path(".reports/benchmark/latest.json")),
    with_ollama: bool = typer.Option(False, "--with-ollama"),
    ollama_model: str = typer.Option("qwen2.5:0.5b", "--ollama-model"),
    ollama_base_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-base-url"),
    ollama_config: Path = typer.Option(Path("configs/benchmark_ollama.yaml")),
    ollama_prompt_config: Path = typer.Option(Path("configs/benchmark_ollama_prompt.yaml")),
    harness_weight: float | None = typer.Option(None, min=0.0, max=1.0),
    enforce_thresholds_flag: bool = typer.Option(False, "--enforce-thresholds"),
    thresholds_config: Path = typer.Option(Path("configs/benchmark_thresholds.yaml")),
    skip_history: bool = typer.Option(False, "--skip-history"),
) -> None:
    ollama_settings = None
    prompt_settings = None
    if with_ollama:
        base_settings = load_ollama_benchmark_config(ollama_config)
        ollama_settings = OllamaBenchmarkConfig(
            base_url=ollama_base_url,
            model=ollama_model,
            timeout_seconds=base_settings.timeout_seconds,
            harness_weight=harness_weight if harness_weight is not None else base_settings.harness_weight,
            input_usd_per_1m=base_settings.input_usd_per_1m,
            output_usd_per_1m=base_settings.output_usd_per_1m,
        )
        if ollama_prompt_config.exists():
            prompt_settings = load_ollama_prompt_config(ollama_prompt_config)
    try:
        report = run_golden_benchmark(
            tasks_root=tasks_root,
            benchmark_id=benchmark_id,
            run_id=run_id,
            ollama_config=ollama_settings,
            ollama_prompt_config=prompt_settings,
        )
    except OllamaError as exc:
        typer.echo(f"FAIL ollama {exc}")
        raise typer.Exit(code=1) from exc
    written = write_benchmark_report(
        report,
        output,
        append_history=not skip_history,
    )
    status = "PASS" if report.aggregate.fail_count == 0 else "FAIL"
    mode = report.run_mode
    model_suffix = f" model={report.ollama_model}" if report.ollama_model else ""
    typer.echo(
        f"{status} benchmark_run id={report.benchmark_id} run={report.run_id} mode={mode}{model_suffix} "
        f"score={report.aggregate.system_score} harness={report.aggregate.harness_system_score} "
        f"tier={report.aggregate.tier} passed={report.aggregate.pass_count}/{report.aggregate.total}"
    )
    if report.aggregate.llm_system_score is not None:
        typer.echo(f"LLM_SCORE {report.aggregate.llm_system_score}")
    if report.cost.total_tokens > 0:
        typer.echo(
            "COST "
            f"input_tokens={report.cost.total_input_tokens} "
            f"output_tokens={report.cost.total_output_tokens} "
            f"total_tokens={report.cost.total_tokens} "
            f"latency_ms={report.cost.total_latency_ms} "
            f"output_tps={report.cost.output_tokens_per_second} "
            f"usd={report.cost.estimated_cost_usd}"
        )
    typer.echo(f"REPORT {written}")
    summary_path = output.parent / f"{report.run_id}_summary.md"
    if summary_path.exists():
        typer.echo(f"SUMMARY {summary_path}")
    typer.echo(render_summary_table(report))
    for task in report.tasks:
        item_status = task.result.upper()
        token_suffix = ""
        if task.token_usage is not None:
            token_suffix = (
                f" in={task.token_usage.input_tokens} out={task.token_usage.output_tokens} "
                f"usd={task.token_usage.estimated_cost_usd}"
            )
        llm_suffix = (
            f" llm={task.llm_system_score:.2f}" if task.llm_system_score is not None else ""
        )
        typer.echo(
            f"{item_status} {task.task_id} category={task.category} "
            f"harness={task.harness_system_score:.2f}{llm_suffix} blend={task.system_score:.2f} "
            f"failures={len(task.failures)}{token_suffix}"
        )
    exit_code = 1 if report.aggregate.fail_count > 0 else 0
    if enforce_thresholds_flag:
        thresholds = load_benchmark_thresholds(thresholds_config)
        violations = enforce_thresholds(report, thresholds)
        if violations:
            typer.echo("THRESHOLD_FAIL")
            for violation in violations:
                typer.echo(f"  {violation}")
            exit_code = 1
        else:
            typer.echo("THRESHOLD_PASS")
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command("benchmark-replay")
def benchmark_replay(
    run: Path | None = typer.Option(None, "--run", help="Path to benchmark JSON report"),
    run_id: str | None = typer.Option(None, "--run-id"),
    report_dir: Path = typer.Option(Path(".reports/benchmark"), "--dir"),
    llm_alert_below: float = typer.Option(0.70, "--llm-alert-below", min=0.0, max=1.0),
    only_flagged: bool = typer.Option(False, "--only-flagged"),
) -> None:
    if run is None:
        if run_id is None:
            run = report_dir / "latest.json"
        else:
            run = report_dir / f"{run_id}.json"
            if not run.exists():
                candidates = sorted(report_dir.glob(f"{run_id}*.json"))
                if candidates:
                    run = candidates[0]
    if run is None or not run.exists():
        typer.echo("FAIL benchmark_replay report not found")
        raise typer.Exit(code=1)
    report = load_benchmark_report(run)
    typer.echo(
        render_replay_report(
            report,
            llm_alert_below=llm_alert_below,
            only_flagged=only_flagged,
        )
    )


@app.command("benchmark-trend")
def benchmark_trend(
    history: Path = typer.Option(Path(".reports/benchmark/history.jsonl")),
    last: int = typer.Option(10, "--last", min=1),
) -> None:
    entries = load_benchmark_history(history, limit=last)
    typer.echo(render_trend_table(entries))


@app.command("benchmark-ollama-check")
def benchmark_ollama_check(
    ollama_model: str = typer.Option("qwen2.5:0.5b", "--ollama-model"),
    ollama_base_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-base-url"),
) -> None:
    client = OllamaClient(OllamaConfig(base_url=ollama_base_url, model=ollama_model))
    if not client.health_check():
        typer.echo(f"FAIL ollama_unreachable base_url={ollama_base_url}")
        raise typer.Exit(code=1)
    models = client.list_models()
    typer.echo(f"PASS ollama_reachable models={len(models)}")
    for name in models:
        typer.echo(f"MODEL {name}")
    try:
        client.ensure_model(ollama_model)
    except OllamaError as exc:
        typer.echo(f"FAIL {exc}")
        raise typer.Exit(code=1) from exc
    probe = client.chat(system="Reply with DECISION: continue", user="health check")
    typer.echo(
        f"PASS ollama_model model={ollama_model} latency_ms={probe.latency_ms} "
        f"input_tokens={probe.token_usage.input_tokens} "
        f"output_tokens={probe.token_usage.output_tokens} "
        f"source={probe.token_usage.token_source} "
        f"preview={probe.content[:80]!r}"
    )


@app.command()
def doctor(
    root: Path = typer.Option(Path(".")),
    ollama_model: str = typer.Option("qwen2.5:0.5b", "--ollama-model"),
    ollama_base_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-base-url"),
    skip_ollama: bool = typer.Option(False, "--skip-ollama"),
    skip_ripgrep: bool = typer.Option(False, "--skip-ripgrep"),
) -> None:
    report = run_doctor(
        root=root,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
        check_ollama=not skip_ollama,
        check_ripgrep=not skip_ripgrep,
    )
    status = "PASS" if report.passed else "FAIL"
    typer.echo(f"{status} doctor checks={len(report.checks)}")
    for check in report.checks:
        item_status = "PASS" if check.passed else "FAIL"
        typer.echo(f"{item_status} {check.name} {check.detail}")
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def phase_fast_gate(
    config: Path = typer.Option(Path("configs/phase_fast_gates.yaml")),
    root: Path = typer.Option(Path(".")),
    workspace_root: Path = typer.Option(Path(".reports/phase-fast-gate")),
    output: Path | None = typer.Option(None),
    clean: bool = typer.Option(False, "--clean"),
    unique_workspace: bool = typer.Option(False, "--unique-workspace"),
) -> None:
    summary = run_phase_fast_gates(
        config_path=config,
        root=root,
        workspace_root=workspace_root,
        clean=clean,
        unique_workspace=unique_workspace,
    )
    if output is not None:
        write_phase_fast_gate_report(summary, output)
    status = "PASS" if summary.passed else "FAIL"
    typer.echo(
        f"{status} phase_fast_gate source={summary.source_ref} "
        f"passed={summary.passed_count}/{summary.total}"
    )
    if output is not None:
        typer.echo(f"REPORT {output}")
    for result in summary.results:
        item_status = "PASS" if result.passed else "FAIL"
        typer.echo(
            f"{item_status} {result.phase}.{result.id} "
            f"runner={result.runner} {result.summary}"
        )
    if not summary.passed:
        raise typer.Exit(code=1)























if __name__ == "__main__":
    app()
