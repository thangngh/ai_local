from __future__ import annotations

import shutil
from pathlib import Path

from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.skills.models import (
    SkillInstallDecision,
    SkillInstallRequest,
    SkillInstallResult,
    SkillNextGate,
)


def install_skill_package(
    request: SkillInstallRequest,
    *,
    audit_store: InMemoryAuditStore | None = None,
) -> SkillInstallResult:
    result = _install_skill_package(request)
    if audit_store is not None:
        audit_store.append(
            make_audit_event(
                "skill.install.apply",
                request.lifecycle.package_id or "unknown-package",
                result.decision,
            )
        )
    return result


def _install_skill_package(request: SkillInstallRequest) -> SkillInstallResult:
    lifecycle = request.lifecycle
    if lifecycle.decision == "quarantine":
        return _install_result(request, "quarantined", "lifecycle quarantined package", "quarantine")
    if lifecycle.decision not in {"allow_install", "allow_update"}:
        return _install_result(
            request,
            "denied",
            "installer requires allowed lifecycle decision",
            "request_lifecycle",
        )

    source_dir = Path(request.source_dir).resolve()
    staging_root = Path(request.staging_root).resolve()
    controlled_root = Path(request.controlled_root).resolve()
    if lifecycle.controlled_root is not None and Path(lifecycle.controlled_root).resolve() != controlled_root:
        return _install_result(
            request,
            "denied",
            "installer controlled root must match lifecycle root",
            "request_lifecycle",
        )
    if not source_dir.is_dir():
        return _install_result(request, "denied", "package source directory is missing", "knowledge_gate")
    if not (source_dir / "SKILL.md").is_file():
        return _install_result(request, "denied", "package source missing SKILL.md", "knowledge_gate")

    package_name = _package_dir_name(request)
    target_dir = (controlled_root / package_name).resolve()
    staging_dir = (staging_root / f"{package_name}.stage").resolve()
    rollback_dir = (staging_root / f"{package_name}.rollback").resolve()
    if not _is_relative_to(target_dir, controlled_root):
        return _install_result(request, "denied", "target escapes controlled skill root", "stop")
    if not _is_relative_to(staging_dir, staging_root) or not _is_relative_to(rollback_dir, staging_root):
        return _install_result(request, "denied", "staging path escapes staging root", "stop")
    if lifecycle.decision == "allow_install" and target_dir.exists():
        return _install_result(request, "denied", "install target already exists", "patch_pipeline")
    if lifecycle.decision == "allow_update" and not target_dir.exists():
        return _install_result(request, "denied", "update target is missing", "patch_pipeline")

    staging_root.mkdir(parents=True, exist_ok=True)
    controlled_root.mkdir(parents=True, exist_ok=True)
    _remove_tree(staging_dir)
    _remove_tree(rollback_dir)

    try:
        shutil.copytree(source_dir, staging_dir)
        if target_dir.exists():
            shutil.move(str(target_dir), str(rollback_dir))
        if request.simulate_failure:
            raise RuntimeError("simulated installer failure")
        shutil.move(str(staging_dir), str(target_dir))
    except Exception:
        rolled_back = _rollback_install(target_dir, staging_dir, rollback_dir)
        if rolled_back:
            return _install_result(
                request,
                "rolled_back",
                "installer failed and rollback restored previous package",
                "patch_pipeline",
                target_dir=target_dir,
                staging_dir=staging_dir,
                rollback_dir=rollback_dir,
            )
        return _install_result(
            request,
            "denied",
            "installer failed without rollback path",
            "stop",
            target_dir=target_dir,
            staging_dir=staging_dir,
            rollback_dir=rollback_dir,
        )

    decision: SkillInstallDecision = "updated" if lifecycle.decision == "allow_update" else "installed"
    reason = "skill package updated atomically" if decision == "updated" else "skill package installed atomically"
    return _install_result(
        request,
        decision,
        reason,
        "evidence_rank",
        target_dir=target_dir,
        staging_dir=staging_dir,
        rollback_dir=rollback_dir if rollback_dir.exists() else None,
    )


def _rollback_install(target_dir: Path, staging_dir: Path, rollback_dir: Path) -> bool:
    _remove_tree(staging_dir)
    if target_dir.exists():
        _remove_tree(target_dir)
    if rollback_dir.exists():
        shutil.move(str(rollback_dir), str(target_dir))
        return True
    return False


def _remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _package_dir_name(request: SkillInstallRequest) -> str:
    requested = request.package_dir_name or request.lifecycle.skill_id or request.lifecycle.package_id
    if not requested:
        return "unknown-skill"
    return requested.replace("\\", "-").replace("/", "-").replace("..", "-").strip() or "unknown-skill"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _install_result(
    request: SkillInstallRequest,
    decision: SkillInstallDecision,
    reason: str,
    next_gate: SkillNextGate,
    *,
    target_dir: Path | None = None,
    staging_dir: Path | None = None,
    rollback_dir: Path | None = None,
) -> SkillInstallResult:
    return SkillInstallResult(
        package_id=request.lifecycle.package_id,
        skill_id=request.lifecycle.skill_id,
        decision=decision,
        reason=reason,
        target_dir=str(target_dir) if target_dir is not None else None,
        staging_dir=str(staging_dir) if staging_dir is not None else None,
        rollback_dir=str(rollback_dir) if rollback_dir is not None else None,
        audit_required=True,
        next_gate=next_gate,
    )
