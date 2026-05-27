from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from typing import Any

from ai_local.agent.state import AgentRun, AgentRunStatus
from ai_local.agent.operations import cancel_agent_run, stop_agent_run
from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore, make_audit_event
from ai_local.config.loader import load_yaml
from ai_local.harness.agent_loop_gate import run_agent_loop_promotion
from ai_local.harness.confirmation_gate import run_confirmation_promotion
from ai_local.harness.conflict_path_gate import run_conflict_path_promotion
from ai_local.harness.evaluation_gate import run_evaluation_promotion
from ai_local.harness.evidence_rank_gate import run_evidence_rank_promotion
from ai_local.harness.knowledge_gate import run_knowledge_promotion
from ai_local.harness.memory_governance_gate import run_memory_governance_promotion
from ai_local.harness.memory_sql_gate import run_memory_sql_promotion
from ai_local.harness.operational_safety_gate import run_operational_safety_promotion
from ai_local.harness.patch_pipeline_harness import run_patch_pipeline_promotion
from ai_local.harness.prompt_injection_refusal_gate import (
    run_prompt_injection_refusal_promotion,
)
from ai_local.harness.request_lifecycle_gate import run_request_lifecycle_promotion
from ai_local.harness.retrieval_gate import run_retrieval_promotion
from ai_local.harness.skill_gate import run_skill_promotion
from ai_local.harness.thread_control_gate import run_thread_control_promotion
from ai_local.harness.tool_combo_gate import run_tool_combo_promotion
from ai_local.pipeline.phase9_close import run_phase9_close
from ai_local.queue.models import Job, JobStatus
from ai_local.queue.operations import cancel_queue_job, retry_dead_letter_job
from ai_local.queue.store import SQLiteQueueStore
from ai_local.runtime.control_plane import build_runtime_control_snapshot
from ai_local.runtime.tui import run_runtime_tui_frames
from ai_local.runtime.backup import create_runtime_backup, restore_runtime_backup
from ai_local.tools.sandbox import (
    SandboxPolicy,
    SandboxRunRequest,
    SubprocessSandboxAdapter,
)


@dataclass(frozen=True)
class PhaseFastGateCase:
    id: str
    phase: str
    runner: str
    max_level: str | None = None


@dataclass(frozen=True)
class PhaseFastGateResult:
    id: str
    phase: str
    runner: str
    passed: bool
    summary: str


@dataclass(frozen=True)
class PhaseFastGateSummary:
    passed: bool
    source_ref: str
    total: int
    passed_count: int
    results: list[PhaseFastGateResult]
    generated_at: str
    workspace_root: str


_LEVEL_CONFIGS: dict[str, Path] = {
    "agent_loop": Path("configs/agent_loop_gates.yaml"),
    "confirmation": Path("configs/confirmation_gates.yaml"),
    "conflict_paths": Path("configs/conflict_path_gates.yaml"),
    "evaluation": Path("configs/evaluation_gates.yaml"),
    "evidence_rank": Path("configs/evidence_rank_gates.yaml"),
    "knowledge": Path("configs/knowledge_gates.yaml"),
    "memory_governance": Path("configs/memory_governance_gates.yaml"),
    "memory_sql": Path("configs/memory_sql_gates.yaml"),
    "operational_safety": Path("configs/operational_safety_gates.yaml"),
    "patch_pipeline": Path("configs/patch_pipeline_harness.yaml"),
    "prompt_injection": Path("configs/prompt_injection_refusal_gates.yaml"),
    "request_lifecycle": Path("configs/request_lifecycle_gates.yaml"),
    "retrieval": Path("configs/retrieval_gates.yaml"),
    "thread_control": Path("configs/thread_control_gates.yaml"),
    "tool_combo": Path("configs/tool_combo_gates.yaml"),
}


def load_phase_fast_gate_cases(config_path: Path) -> tuple[str, list[PhaseFastGateCase]]:
    data = load_yaml(config_path)
    config = data.get("phase_fast_gates", {})
    if not isinstance(config, dict):
        msg = f"Invalid phase fast gate config in {config_path}"
        raise ValueError(msg)
    cases = [
        PhaseFastGateCase(
            id=str(item["id"]),
            phase=str(item["phase"]),
            runner=str(item["runner"]),
            max_level=str(item["max_level"]) if "max_level" in item else None,
        )
        for item in config.get("gates", [])
        if isinstance(item, dict)
    ]
    return str(config.get("source_ref", "")), cases


def prepare_phase_fast_workspace(
    workspace_root: Path,
    *,
    clean: bool = False,
    unique: bool = False,
) -> Path:
    if unique:
        resolved = workspace_root / f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
    else:
        resolved = workspace_root
    if clean and resolved.exists():
        shutil.rmtree(resolved, ignore_errors=True)
    if clean and resolved.exists():
        try:
            next(resolved.iterdir())
            resolved = workspace_root / f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        except StopIteration:
            pass
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def run_phase_fast_gates(
    *,
    config_path: Path,
    root: Path,
    workspace_root: Path,
    clean: bool = False,
    unique_workspace: bool = False,
) -> PhaseFastGateSummary:
    resolved_workspace = prepare_phase_fast_workspace(
        workspace_root,
        clean=clean or unique_workspace,
        unique=unique_workspace,
    )
    source_ref, cases = load_phase_fast_gate_cases(config_path)
    results = [
        _run_case(case, root=root, workspace_root=resolved_workspace) for case in cases
    ]
    passed_count = sum(1 for result in results if result.passed)
    return PhaseFastGateSummary(
        passed=passed_count == len(results),
        source_ref=source_ref,
        total=len(results),
        passed_count=passed_count,
        results=results,
        generated_at=datetime.now(UTC).isoformat(),
        workspace_root=str(resolved_workspace),
    )


def phase_fast_gate_report(summary: PhaseFastGateSummary) -> dict[str, object]:
    return {
        "passed": summary.passed,
        "source_ref": summary.source_ref,
        "total": summary.total,
        "passed_count": summary.passed_count,
        "generated_at": summary.generated_at,
        "workspace_root": summary.workspace_root,
        "results": [
            {
                "id": result.id,
                "phase": result.phase,
                "runner": result.runner,
                "passed": result.passed,
                "summary": result.summary,
            }
            for result in summary.results
        ],
    }


def write_phase_fast_gate_report(summary: PhaseFastGateSummary, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(phase_fast_gate_report(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_case(case: PhaseFastGateCase, *, root: Path, workspace_root: Path) -> PhaseFastGateResult:
    if case.runner == "skills":
        return _run_skill_case(case, root=root)
    if case.runner in _LEVEL_CONFIGS:
        return _run_level_case(case, root=root)
    if case.runner == "phase9_close":
        return _run_phase9_close_case(case, workspace_root=workspace_root)
    if case.runner == "runtime_store_smoke":
        return _runtime_store_smoke(case, workspace_root=workspace_root)
    if case.runner == "runtime_schema_smoke":
        return _runtime_schema_smoke(case, workspace_root=workspace_root)
    if case.runner == "tool_sandbox_smoke":
        return _tool_sandbox_smoke(case, workspace_root=workspace_root)
    if case.runner == "runtime_control_smoke":
        return _runtime_control_smoke(case, workspace_root=workspace_root)
    if case.runner == "runtime_tui_smoke":
        return _runtime_tui_smoke(case, workspace_root=workspace_root)
    if case.runner == "queue_operations_smoke":
        return _queue_operations_smoke(case, workspace_root=workspace_root)
    if case.runner == "agent_run_operations_smoke":
        return _agent_run_operations_smoke(case, workspace_root=workspace_root)
    if case.runner == "runtime_backup_restore_smoke":
        return _runtime_backup_restore_smoke(case, workspace_root=workspace_root)
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=False,
        summary="unknown fast gate runner",
    )


def _run_level_case(case: PhaseFastGateCase, *, root: Path) -> PhaseFastGateResult:
    relative_config = _LEVEL_CONFIGS[case.runner]
    level_results = _call_level_runner(
        case.runner,
        config_path=root / relative_config,
        max_level=case.max_level,
    )
    passed = all(result.passed for result in level_results)
    deepest = level_results[-1].level if level_results else "none"
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary=f"levels={len(level_results)} deepest={deepest}",
    )


def _call_level_runner(
    runner: str,
    *,
    config_path: Path,
    max_level: str | None,
) -> list[Any]:
    if runner == "agent_loop":
        return list(run_agent_loop_promotion(config_path=config_path, max_level=max_level))
    if runner == "confirmation":
        return list(run_confirmation_promotion(config_path=config_path, max_level=max_level))
    if runner == "conflict_paths":
        return list(run_conflict_path_promotion(config_path=config_path, max_level=max_level))
    if runner == "evaluation":
        return list(run_evaluation_promotion(config_path=config_path, max_level=max_level))
    if runner == "evidence_rank":
        return list(run_evidence_rank_promotion(config_path=config_path, max_level=max_level))
    if runner == "knowledge":
        return list(run_knowledge_promotion(config_path=config_path, max_level=max_level))
    if runner == "memory_governance":
        return list(run_memory_governance_promotion(config_path=config_path, max_level=max_level))
    if runner == "memory_sql":
        return list(run_memory_sql_promotion(config_path=config_path, max_level=max_level))
    if runner == "operational_safety":
        return list(run_operational_safety_promotion(config_path=config_path, max_level=max_level))
    if runner == "patch_pipeline":
        return list(run_patch_pipeline_promotion(config_path=config_path, max_level=max_level))
    if runner == "prompt_injection":
        return list(
            run_prompt_injection_refusal_promotion(
                config_path=config_path,
                max_level=max_level,
            )
        )
    if runner == "request_lifecycle":
        return list(run_request_lifecycle_promotion(config_path=config_path, max_level=max_level))
    if runner == "retrieval":
        return list(run_retrieval_promotion(config_path=config_path, max_level=max_level))
    if runner == "thread_control":
        return list(run_thread_control_promotion(config_path=config_path, max_level=max_level))
    if runner == "tool_combo":
        return list(run_tool_combo_promotion(config_path=config_path, max_level=max_level))
    return []


def _run_skill_case(case: PhaseFastGateCase, *, root: Path) -> PhaseFastGateResult:
    level_results = run_skill_promotion(
        config_path=root / "configs/skill_gates.yaml",
        root=root,
        max_level=case.max_level,
    )
    passed = all(result.passed for result in level_results)
    deepest = level_results[-1].level if level_results else "none"
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary=f"levels={len(level_results)} deepest={deepest}",
    )


def _run_phase9_close_case(case: PhaseFastGateCase, *, workspace_root: Path) -> PhaseFastGateResult:
    result = run_phase9_close(
        replay_config=Path("configs/phase9_replay_fixtures.yaml"),
        stress_config=Path("configs/phase9_stress_gates.yaml"),
        workspace_root=workspace_root / "phase9-close",
        patch_levels_config=Path("configs/patch_levels.yaml"),
        audit_db=workspace_root / "phase9-close" / "audit.db",
    )
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=result.passed,
        summary=(
            f"replay={result.replay_passed}/{result.replay_total} "
            f"stress={result.stress_passed}/{result.stress_total}"
        ),
    )


def _runtime_store_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    tasks_db = workspace_root / "runtime-store" / "tasks.db"
    audit_db = workspace_root / "runtime-store" / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(Job(id="fast-job", type="phase10", payload={}))
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="fast-run", goal="fast gate", status=AgentRunStatus.PENDING)
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.fast", "runtime", "ok"))
    passed = (
        SQLiteQueueStore(tasks_db).status_counts().get("pending") == 1
        and SQLiteAgentRunStore(tasks_db).status_counts().get("pending") == 1
        and SQLiteAuditStore(audit_db).count() == 1
    )
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary="persistent runtime stores smoke",
    )


def _runtime_schema_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    tasks_db = workspace_root / "runtime-schema" / "tasks.db"
    audit_db = workspace_root / "runtime-schema" / "audit.db"
    versions = {
        **SQLiteQueueStore(tasks_db).schema_versions(),
        **SQLiteAgentRunStore(tasks_db).schema_versions(),
        **SQLiteAuditStore(audit_db).schema_versions(),
    }
    passed = versions == {"agent_runs": 1, "audit": 1, "queue": 1}
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary=f"schema_versions={versions}",
    )


def _tool_sandbox_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    root = workspace_root / "tool-sandbox"
    root.mkdir(parents=True, exist_ok=True)
    result = SubprocessSandboxAdapter().run(
        SandboxRunRequest(
            command=[sys.executable, "-c", "print('phase10-fast')"],
            cwd=root,
            timeout_seconds=5,
            policy=SandboxPolicy(
                workspace_root=root,
                max_timeout_seconds=5,
                allowed_executables=frozenset({sys.executable, Path(sys.executable).name}),
            ),
        )
    )
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=result.decision == "succeeded" and result.stdout.strip() == "phase10-fast",
        summary=f"sandbox_decision={result.decision}",
    )


def _runtime_control_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    tasks_db = workspace_root / "runtime-control" / "tasks.db"
    audit_db = workspace_root / "runtime-control" / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(id="control-job", type="phase10", status=JobStatus.SUCCEEDED, payload={})
    )
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="control-run", goal="control", status=AgentRunStatus.SUCCEEDED)
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase10.control", "runtime", "ok"))
    snapshot = build_runtime_control_snapshot(tasks_db=tasks_db, audit_db=audit_db)
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=snapshot.health == "ok",
        summary=f"runtime_control_health={snapshot.health}",
    )


def _runtime_tui_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    tasks_db = workspace_root / "runtime-tui" / "tasks.db"
    audit_db = workspace_root / "runtime-tui" / "audit.db"
    SQLiteQueueStore(tasks_db).enqueue(
        Job(id="tui-job", type="phase11", status=JobStatus.SUCCEEDED, payload={})
    )
    SQLiteAgentRunStore(tasks_db).create(
        AgentRun(id="tui-run", goal="render tui", status=AgentRunStatus.SUCCEEDED)
    )
    SQLiteAuditStore(audit_db).append(make_audit_event("phase11.tui", "runtime", "ok"))
    frames = run_runtime_tui_frames(tasks_db=tasks_db, audit_db=audit_db, iterations=1)
    passed = (
        len(frames) == 1
        and frames[0].health == "ok"
        and "AI LOCAL RUNTIME" in frames[0].text
        and "[queue]" in frames[0].text
        and "[agent-runs]" in frames[0].text
    )
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary=f"runtime_tui_health={frames[0].health if frames else 'missing'}",
    )


def _queue_operations_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    tasks_db = workspace_root / "queue-operations" / "tasks.db"
    audit_db = workspace_root / "queue-operations" / "audit.db"
    queue = SQLiteQueueStore(tasks_db)
    queue.enqueue(
        Job(
            id="retry-job",
            type="phase11",
            status=JobStatus.DEAD_LETTER,
            payload={},
            attempts=2,
            last_error="boom",
        )
    )
    queue.enqueue(Job(id="cancel-job", type="phase11", payload={}))
    retry = retry_dead_letter_job(tasks_db=tasks_db, audit_db=audit_db, job_id="retry-job")
    cancel = cancel_queue_job(tasks_db=tasks_db, audit_db=audit_db, job_id="cancel-job")
    retry_job = queue.get("retry-job")
    cancel_job = queue.get("cancel-job")
    audit_count = SQLiteAuditStore(audit_db).count()
    passed = (
        retry.decision == "succeeded"
        and cancel.decision == "succeeded"
        and retry_job is not None
        and retry_job.status == JobStatus.PENDING
        and cancel_job is not None
        and cancel_job.status == JobStatus.CANCELLED
        and audit_count == 2
    )
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary=f"queue_operations retry={retry.decision} cancel={cancel.decision}",
    )


def _agent_run_operations_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    tasks_db = workspace_root / "agent-run-operations" / "tasks.db"
    audit_db = workspace_root / "agent-run-operations" / "audit.db"
    store = SQLiteAgentRunStore(tasks_db)
    store.create(AgentRun(id="stop-run", goal="stop", status=AgentRunStatus.RUNNING))
    store.create(AgentRun(id="cancel-run", goal="cancel", status=AgentRunStatus.WAITING_USER))
    stop = stop_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id="stop-run")
    cancel = cancel_agent_run(tasks_db=tasks_db, audit_db=audit_db, run_id="cancel-run")
    stopped = store.get("stop-run")
    cancelled = store.get("cancel-run")
    audit_count = SQLiteAuditStore(audit_db).count()
    passed = (
        stop.decision == "succeeded"
        and cancel.decision == "succeeded"
        and stopped is not None
        and stopped.status == AgentRunStatus.STOPPED
        and cancelled is not None
        and cancelled.status == AgentRunStatus.CANCELLED
        and audit_count == 2
    )
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary=f"agent_run_operations stop={stop.decision} cancel={cancel.decision}",
    )


def _runtime_backup_restore_smoke(
    case: PhaseFastGateCase,
    *,
    workspace_root: Path,
) -> PhaseFastGateResult:
    source_tasks = workspace_root / "runtime-backup-source" / "tasks.db"
    source_audit = workspace_root / "runtime-backup-source" / "audit.db"
    target_tasks = workspace_root / "runtime-backup-target" / "tasks.db"
    target_audit = workspace_root / "runtime-backup-target" / "audit.db"
    backup_dir = workspace_root / "runtime-backup"
    SQLiteQueueStore(source_tasks).enqueue(Job(id="backup-job", type="phase11", payload={}))
    SQLiteAgentRunStore(source_tasks).create(AgentRun(id="backup-run", goal="backup"))
    SQLiteAuditStore(source_audit).append(make_audit_event("phase11.backup", "runtime", "ok"))
    backup = create_runtime_backup(
        tasks_db=source_tasks,
        audit_db=source_audit,
        backup_dir=backup_dir,
    )
    restore = restore_runtime_backup(
        backup_dir=backup_dir,
        tasks_db=target_tasks,
        audit_db=target_audit,
    )
    passed = (
        backup.decision == "succeeded"
        and restore.decision == "succeeded"
        and SQLiteQueueStore(target_tasks).get("backup-job") is not None
        and SQLiteAgentRunStore(target_tasks).get("backup-run") is not None
        and SQLiteAuditStore(target_audit).count() == 1
    )
    return PhaseFastGateResult(
        id=case.id,
        phase=case.phase,
        runner=case.runner,
        passed=passed,
        summary=f"runtime_backup backup={backup.decision} restore={restore.decision}",
    )
