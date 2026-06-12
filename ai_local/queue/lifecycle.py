from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_local.llm.ollama import OllamaClient, OllamaError
from ai_local.queue.models import JobStatus
from ai_local.queue.store import SQLiteQueueStore

_FORBIDDEN_APPLY_PARTS = {
    ".ai-local",
    ".git",
    ".next",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}
_MAX_APPLY_FILES = 3
_MAX_APPLY_CHANGED_LINES = 240


@dataclass(frozen=True)
class TaskLifecycleResult:
    decision: str
    reason: str
    job_id: str
    status: JobStatus | None = None
    details: dict[str, Any] = field(default_factory=dict)


def approve_task(*, tasks_db: Path, reports_dir: Path, job_id: str) -> TaskLifecycleResult:
    queue = SQLiteQueueStore(tasks_db)
    job = queue.get(job_id)
    if job is None:
        return TaskLifecycleResult("denied", "job not found", job_id)
    if job.status != JobStatus.PROPOSAL_READY:
        return TaskLifecycleResult("denied", f"expected proposal_ready, got {job.status.value}", job_id, job.status)
    artifact = _load_artifact(reports_dir, job_id)
    artifact["approved_at"] = _now()
    artifact["execution_state"] = "approved"
    _write_artifact(reports_dir, job_id, artifact)
    updated = queue.replace(job.model_copy(update={"status": JobStatus.APPROVED}))
    return TaskLifecycleResult("approved", "proposal approved", job_id, updated.status)


def propose_task(
    *,
    workspace: Path,
    tasks_db: Path,
    knowledge_db: Path,
    reports_dir: Path,
    job_id: str,
    ollama_client: OllamaClient,
) -> TaskLifecycleResult:
    queue = SQLiteQueueStore(tasks_db)
    job = queue.get(job_id)
    if job is None:
        return TaskLifecycleResult("denied", "job not found", job_id)
    if job.status not in {JobStatus.PROPOSAL_READY, JobStatus.APPROVED}:
        return TaskLifecycleResult("denied", f"expected proposal_ready or approved, got {job.status.value}", job_id, job.status)

    from ai_local.runtime.worker_contract import _llm_analyze_task, _search_index, _search_knowledge

    task_text = str(job.payload.get("task", job.payload.get("query", "")))
    if not task_text:
        return TaskLifecycleResult("denied", "job payload has no task/query text", job_id, job.status)
    knowledge_context = _search_knowledge(knowledge_db, task_text)
    index_context = _search_index(knowledge_db, task_text)
    kh_notes = [item for item in knowledge_context if item.get("kind") == "note"]
    try:
        llm_result = _llm_analyze_task(ollama_client, task_text, kh_notes, index_context)
    except (OllamaError, json.JSONDecodeError) as exc:
        return TaskLifecycleResult("denied", f"LLM proposal failed: {exc}", job_id, job.status)

    changes = llm_result.get("changes", [])
    if not isinstance(changes, list):
        return TaskLifecycleResult("denied", "LLM proposal returned invalid changes", job_id, job.status)

    artifact = _load_artifact(reports_dir, job_id)
    artifact.update(
        {
            "job_id": job_id,
            "task_summary": task_text[:300],
            "llm_used": True,
            "llm_analysis": llm_result.get("analysis", ""),
            "llm_reasoning": llm_result.get("reasoning", ""),
            "code_changes": changes,
            "code_changes_note": (
                "These changes are suggestions for user review. "
                "They have NOT been applied."
            ),
            "proposal_updated_at": _now(),
            "execution_state": "proposal_ready",
            "applied": False,
            "context_count": {
                "knowledge_notes": len(kh_notes),
                "knowledge_files": len([item for item in knowledge_context if item.get("kind") == "file"]),
                "index_hits": len(index_context),
            },
        }
    )
    _write_artifact(reports_dir, job_id, artifact)
    updated = queue.replace(job.model_copy(update={"status": JobStatus.PROPOSAL_READY}))
    return TaskLifecycleResult(
        "proposed",
        "code change proposal generated",
        job_id,
        updated.status,
        {"changes": len(changes)},
    )


def propose_task_deterministic(
    *,
    workspace: Path,
    tasks_db: Path,
    reports_dir: Path,
    job_id: str,
) -> TaskLifecycleResult:
    queue = SQLiteQueueStore(tasks_db)
    job = queue.get(job_id)
    if job is None:
        return TaskLifecycleResult("denied", "job not found", job_id)
    if job.status not in {JobStatus.PROPOSAL_READY, JobStatus.APPROVED}:
        return TaskLifecycleResult("denied", f"expected proposal_ready or approved, got {job.status.value}", job_id, job.status)

    task_text = str(job.payload.get("task", job.payload.get("query", "")))
    changes = _deterministic_code_changes(workspace, task_text)
    if not changes:
        return TaskLifecycleResult("denied", "no deterministic proposal available for this task", job_id, job.status)

    artifact = _load_artifact(reports_dir, job_id)
    artifact.update(
        {
            "job_id": job_id,
            "task_summary": task_text[:300],
            "llm_used": False,
            "proposal_engine": "deterministic",
            "llm_analysis": "Deterministic demo proposal generated from known pet-store cart-store pattern.",
            "llm_reasoning": "Matched cart/getSubtotal task and prepared a safe comment-only patch.",
            "code_changes": changes,
            "code_changes_note": (
                "These changes are suggestions for user review. "
                "They have NOT been applied."
            ),
            "proposal_updated_at": _now(),
            "execution_state": "proposal_ready",
            "applied": False,
        }
    )
    _write_artifact(reports_dir, job_id, artifact)
    updated = queue.replace(job.model_copy(update={"status": JobStatus.PROPOSAL_READY}))
    return TaskLifecycleResult(
        "proposed",
        "deterministic code change proposal generated",
        job_id,
        updated.status,
        {"changes": len(changes)},
    )


def apply_task(*, workspace: Path, tasks_db: Path, reports_dir: Path, job_id: str) -> TaskLifecycleResult:
    queue = SQLiteQueueStore(tasks_db)
    job = queue.get(job_id)
    if job is None:
        return TaskLifecycleResult("denied", "job not found", job_id)
    if job.status != JobStatus.APPROVED:
        return TaskLifecycleResult("denied", f"expected approved, got {job.status.value}", job_id, job.status)
    artifact = _load_artifact(reports_dir, job_id)
    changes = artifact.get("code_changes")
    if not isinstance(changes, list) or not changes:
        return TaskLifecycleResult("denied", "artifact has no code_changes to apply", job_id, job.status)

    safety = validate_code_changes_for_apply(workspace, changes)
    if not safety.passed:
        return TaskLifecycleResult("denied", safety.reason, job_id, job.status, safety.details)

    applied: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            return TaskLifecycleResult("denied", "invalid code_changes entry", job_id, job.status)
        rel_file = change.get("file")
        original = change.get("original_snippet")
        new = change.get("new_snippet")
        if not isinstance(rel_file, str) or not isinstance(original, str) or not isinstance(new, str):
            return TaskLifecycleResult("denied", "code change must include file/original_snippet/new_snippet", job_id, job.status)
        path = _safe_workspace_path(workspace, rel_file)
        content = path.read_text(encoding="utf-8")
        path.write_text(content.replace(original, new, 1), encoding="utf-8")
        applied.append(rel_file)

    artifact["applied"] = True
    artifact["applied_at"] = _now()
    artifact["execution_state"] = "applied"
    artifact["applied_files"] = applied
    _write_artifact(reports_dir, job_id, artifact)
    updated = queue.replace(job.model_copy(update={"status": JobStatus.APPLIED}))
    return TaskLifecycleResult("applied", "code changes applied", job_id, updated.status, {"files": applied})


def validate_task(
    *,
    workspace: Path,
    tasks_db: Path,
    reports_dir: Path,
    job_id: str,
    commands: list[str] | None = None,
    auto: bool = False,
) -> TaskLifecycleResult:
    queue = SQLiteQueueStore(tasks_db)
    job = queue.get(job_id)
    if job is None:
        return TaskLifecycleResult("denied", "job not found", job_id)
    if job.status not in {JobStatus.APPLIED, JobStatus.APPROVED}:
        return TaskLifecycleResult("denied", f"expected applied or approved, got {job.status.value}", job_id, job.status)

    validation_commands = list(commands or [])
    auto_commands: list[str] = []
    if auto:
        auto_commands = detect_validation_commands(workspace)
        validation_commands.extend(auto_commands)
        if not auto_commands:
            return TaskLifecycleResult("denied", "no validation commands detected", job_id, job.status)

    checks = [_run_validation_command(workspace, command) for command in validation_commands]
    failed = [check for check in checks if check["exit_code"] != 0]
    artifact = _load_artifact(reports_dir, job_id)
    artifact["validated_at"] = _now()
    artifact["validation_auto_commands"] = auto_commands
    artifact["validation_checks"] = checks
    if failed:
        artifact["execution_state"] = "validation_failed"
        _write_artifact(reports_dir, job_id, artifact)
        return TaskLifecycleResult("denied", "validation command failed", job_id, job.status, {"checks": checks})

    artifact["execution_state"] = "validated"
    artifact["validation_note"] = "manual validation recorded" if not checks else "commands passed"
    _write_artifact(reports_dir, job_id, artifact)
    updated = queue.replace(job.model_copy(update={"status": JobStatus.VALIDATED}))
    return TaskLifecycleResult("validated", "validation passed", job_id, updated.status, {"checks": checks})


def detect_validation_commands(workspace: Path) -> list[str]:
    """Detect a conservative validation command set for common project types."""
    commands: list[str] = []
    package_json = workspace / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
        if isinstance(scripts, dict):
            for script in ("test", "lint", "build"):
                if script in scripts:
                    commands.append(f"npm run {script}")
            return commands

    if (workspace / "pyproject.toml").is_file() or (workspace / "pytest.ini").is_file():
        commands.append("python -m pytest")
    elif (workspace / "requirements.txt").is_file():
        commands.append("python -m pytest")
    return commands


def _deterministic_code_changes(workspace: Path, task_text: str) -> list[dict[str, str]]:
    lowered = task_text.lower()
    cart_file = workspace / "src" / "store" / "cart.store.ts"
    if not cart_file.is_file():
        return []
    if not any(term in lowered for term in ("cart", "cartstore", "getsubtotal", "subtotal", "price")):
        return []
    original = "        // NOTE: This is for display only. Final price from server.\n"
    replacement = (
        "        // NOTE: This subtotal is a display-only estimate from local cart state.\n"
        "        // Checkout must request final pricing, discounts, and tax from the server/mock API.\n"
    )
    try:
        content = cart_file.read_text(encoding="utf-8")
    except OSError:
        return []
    if original not in content:
        if replacement not in content:
            return []
        original = replacement
    return [
        {
            "file": "src/store/cart.store.ts",
            "description": "Clarify getSubtotal display-only pricing contract for demo workflow.",
            "original_snippet": original,
            "new_snippet": replacement,
        }
    ]


@dataclass(frozen=True)
class ApplySafetyResult:
    passed: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


def validate_code_changes_for_apply(
    workspace: Path,
    changes: list[Any],
    *,
    max_files: int = _MAX_APPLY_FILES,
    max_changed_lines: int = _MAX_APPLY_CHANGED_LINES,
) -> ApplySafetyResult:
    files: set[str] = set()
    changed_lines = 0
    for index, change in enumerate(changes, start=1):
        if not isinstance(change, dict):
            return ApplySafetyResult(False, f"invalid code_changes entry at index {index}")
        rel_file = change.get("file")
        original = change.get("original_snippet")
        new = change.get("new_snippet")
        if not isinstance(rel_file, str) or not isinstance(original, str) or not isinstance(new, str):
            return ApplySafetyResult(False, f"code change {index} must include file/original_snippet/new_snippet")
        try:
            path = _safe_workspace_path(workspace, rel_file)
        except RuntimeError as exc:
            return ApplySafetyResult(False, str(exc))
        if any(part in _FORBIDDEN_APPLY_PARTS for part in path.relative_to(workspace.resolve()).parts):
            return ApplySafetyResult(False, f"refusing to apply change in generated/runtime path: {rel_file}")
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return ApplySafetyResult(False, str(exc))
        occurrence_count = content.count(original)
        if occurrence_count == 0:
            return ApplySafetyResult(False, f"original snippet not found in {rel_file}")
        if occurrence_count > 1:
            return ApplySafetyResult(False, f"original snippet is ambiguous in {rel_file}")
        files.add(str(path.relative_to(workspace.resolve())))
        changed_lines += max(1, len(original.splitlines()) + len(new.splitlines()))
        if len(files) > max_files:
            return ApplySafetyResult(False, "changed files exceed apply safety limit", {"files": sorted(files)})
        if changed_lines > max_changed_lines:
            return ApplySafetyResult(False, "changed lines exceed apply safety limit", {"changed_lines": changed_lines})
    return ApplySafetyResult(
        True,
        "safe to apply",
        {"files": sorted(files), "changed_lines": changed_lines},
    )


def _artifact_path(reports_dir: Path, job_id: str) -> Path:
    return reports_dir / f"worker-{job_id}.json"


def _load_artifact(reports_dir: Path, job_id: str) -> dict[str, Any]:
    path = _artifact_path(reports_dir, job_id)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_artifact(reports_dir: Path, job_id: str, artifact: dict[str, Any]) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    _artifact_path(reports_dir, job_id).write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _safe_workspace_path(workspace: Path, rel_file: str) -> Path:
    base = workspace.resolve()
    path = (base / rel_file).resolve()
    if base != path and base not in path.parents:
        raise RuntimeError(f"path escapes workspace: {rel_file}")
    if not path.is_file():
        raise RuntimeError(f"file not found: {rel_file}")
    return path


def _run_validation_command(workspace: Path, command: str) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=workspace,
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
