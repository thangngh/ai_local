from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ai_local.agent.store import SQLiteAgentRunStore
from ai_local.audit.store import SQLiteAuditStore
from ai_local.db.schema import list_schema_versions
from ai_local.queue.store import SQLiteQueueStore


RuntimeBackupDecision = Literal["succeeded", "denied"]

_TASK_COMPONENTS = {
    SQLiteQueueStore.COMPONENT: SQLiteQueueStore.TARGET_VERSION,
    SQLiteAgentRunStore.COMPONENT: SQLiteAgentRunStore.TARGET_VERSION,
}
_AUDIT_COMPONENTS = {SQLiteAuditStore.COMPONENT: SQLiteAuditStore.TARGET_VERSION}


@dataclass(frozen=True)
class RuntimeBackupResult:
    decision: RuntimeBackupDecision
    reason: str
    backup_dir: Path
    manifest_path: Path | None = None


def create_runtime_backup(
    *,
    tasks_db: Path,
    audit_db: Path,
    backup_dir: Path,
) -> RuntimeBackupResult:
    _initialize_runtime_dbs(tasks_db=tasks_db, audit_db=audit_db)
    tasks_error = _schema_error(tasks_db, _TASK_COMPONENTS)
    if tasks_error is not None:
        return RuntimeBackupResult("denied", tasks_error, backup_dir)
    audit_error = _schema_error(audit_db, _AUDIT_COMPONENTS)
    if audit_error is not None:
        return RuntimeBackupResult("denied", audit_error, backup_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tasks_db, backup_dir / "tasks.db")
    shutil.copy2(audit_db, backup_dir / "audit.db")
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "files": {
            "tasks_db": "tasks.db",
            "audit_db": "audit.db",
        },
        "schema_versions": {
            "tasks": _schema_versions(tasks_db),
            "audit": _schema_versions(audit_db),
        },
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return RuntimeBackupResult(
        "succeeded",
        "runtime backup created",
        backup_dir,
        manifest_path,
    )


def restore_runtime_backup(
    *,
    backup_dir: Path,
    tasks_db: Path,
    audit_db: Path,
) -> RuntimeBackupResult:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        return RuntimeBackupResult("denied", "backup manifest is missing", backup_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return RuntimeBackupResult("denied", "backup manifest is invalid", backup_dir)

    files = manifest.get("files")
    if not isinstance(files, dict):
        return RuntimeBackupResult("denied", "backup manifest files are invalid", backup_dir)
    backup_tasks = backup_dir / str(files.get("tasks_db", ""))
    backup_audit = backup_dir / str(files.get("audit_db", ""))
    if not backup_tasks.is_file() or not backup_audit.is_file():
        return RuntimeBackupResult("denied", "backup database files are missing", backup_dir)

    tasks_error = _schema_error(backup_tasks, _TASK_COMPONENTS)
    if tasks_error is not None:
        return RuntimeBackupResult("denied", tasks_error, backup_dir, manifest_path)
    audit_error = _schema_error(backup_audit, _AUDIT_COMPONENTS)
    if audit_error is not None:
        return RuntimeBackupResult("denied", audit_error, backup_dir, manifest_path)

    tasks_db.parent.mkdir(parents=True, exist_ok=True)
    audit_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_tasks, tasks_db)
    shutil.copy2(backup_audit, audit_db)
    return RuntimeBackupResult(
        "succeeded",
        "runtime backup restored",
        backup_dir,
        manifest_path,
    )


def _initialize_runtime_dbs(*, tasks_db: Path, audit_db: Path) -> None:
    SQLiteQueueStore(tasks_db).initialize()
    SQLiteAgentRunStore(tasks_db).initialize()
    SQLiteAuditStore(audit_db).initialize()


def _schema_error(db_path: Path, expected: dict[str, int]) -> str | None:
    versions = _schema_versions(db_path)
    for component, target_version in expected.items():
        version = versions.get(component)
        if version != target_version:
            return f"{component} schema is not at supported version {target_version}"
    return None


def _schema_versions(db_path: Path) -> dict[str, int]:
    if not db_path.is_file():
        return {}
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        versions = list_schema_versions(connection)
    return {item.component: item.version for item in versions}
