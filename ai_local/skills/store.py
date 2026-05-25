from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ai_local.skills.loader import parse_skill_markdown


@dataclass(frozen=True)
class InstalledSkillRecord:
    package_id: str
    skill_id: str
    source_ref: str
    checksum: str
    root: str
    skill_path: str
    trusted: bool
    risk_level: str
    audit_ref: str | None
    modified_ns: int


@dataclass(frozen=True)
class InstalledSkillRefreshResult:
    upserted: list[InstalledSkillRecord]
    unchanged: list[str]
    deleted: list[str]
    skipped: list[str]


@dataclass(frozen=True)
class InstalledSkillStats:
    packages: int
    trusted: int
    stale: int


class InstalledSkillStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS installed_skills (
                    package_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    root TEXT NOT NULL,
                    skill_path TEXT NOT NULL,
                    trusted INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    audit_ref TEXT,
                    modified_ns INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_installed_skills_skill_id
                    ON installed_skills(skill_id);
                CREATE INDEX IF NOT EXISTS idx_installed_skills_source_ref
                    ON installed_skills(source_ref);
                """
            )

    def upsert(self, record: InstalledSkillRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO installed_skills(
                    package_id, skill_id, source_ref, checksum, root, skill_path,
                    trusted, risk_level, audit_ref, modified_ns
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_id) DO UPDATE SET
                    skill_id = excluded.skill_id,
                    source_ref = excluded.source_ref,
                    checksum = excluded.checksum,
                    root = excluded.root,
                    skill_path = excluded.skill_path,
                    trusted = excluded.trusted,
                    risk_level = excluded.risk_level,
                    audit_ref = excluded.audit_ref,
                    modified_ns = excluded.modified_ns
                """,
                _record_params(record),
            )

    def delete_package_ids(self, package_ids: list[str]) -> None:
        with self._connect() as connection:
            for package_id in package_ids:
                connection.execute(
                    "DELETE FROM installed_skills WHERE package_id = ?",
                    (package_id,),
                )

    def list_records(self) -> list[InstalledSkillRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM installed_skills ORDER BY package_id"
            )
            return [_record_from_row(row) for row in rows]

    def manifest(self) -> dict[str, InstalledSkillRecord]:
        return {record.package_id: record for record in self.list_records()}

    def stats(self, *, root: Path | None = None) -> InstalledSkillStats:
        records = self.list_records()
        stale = 0
        if root is not None:
            stale = sum(1 for record in records if not (root / record.skill_path).exists())
        return InstalledSkillStats(
            packages=len(records),
            trusted=sum(1 for record in records if record.trusted),
            stale=stale,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


def refresh_installed_skill_registry(
    root: Path,
    store: InstalledSkillStore,
    *,
    audit_ref: str | None = None,
) -> InstalledSkillRefreshResult:
    store.initialize()
    root = root.resolve()
    previous = store.manifest()
    discovered = _discover_installed_skills(root, audit_ref=audit_ref)
    discovered_ids = {record.package_id for record in discovered}
    deleted = sorted(set(previous) - discovered_ids)
    upserted: list[InstalledSkillRecord] = []
    unchanged: list[str] = []
    for record in discovered:
        current = previous.get(record.package_id)
        if current is not None and current.checksum == record.checksum:
            unchanged.append(record.package_id)
            continue
        store.upsert(record)
        upserted.append(record)
    store.delete_package_ids(deleted)
    return InstalledSkillRefreshResult(
        upserted=upserted,
        unchanged=sorted(unchanged),
        deleted=deleted,
        skipped=[],
    )


def cleanup_stale_installed_skills(
    root: Path,
    store: InstalledSkillStore,
) -> list[str]:
    store.initialize()
    root = root.resolve()
    stale = [
        record.package_id
        for record in store.list_records()
        if not (root / record.skill_path).exists()
    ]
    store.delete_package_ids(stale)
    return sorted(stale)


def rebuild_installed_skill_registry(
    root: Path,
    store: InstalledSkillStore,
    *,
    audit_ref: str | None = None,
) -> InstalledSkillRefreshResult:
    store.initialize()
    existing = list(store.manifest())
    store.delete_package_ids(existing)
    result = refresh_installed_skill_registry(root, store, audit_ref=audit_ref)
    return InstalledSkillRefreshResult(
        upserted=result.upserted,
        unchanged=[],
        deleted=existing,
        skipped=result.skipped,
    )


def _discover_installed_skills(
    root: Path,
    *,
    audit_ref: str | None,
) -> list[InstalledSkillRecord]:
    if not root.exists():
        return []
    records: list[InstalledSkillRecord] = []
    for skill_path in sorted(root.glob("*/SKILL.md")):
        definition = parse_skill_markdown(skill_path)
        package_dir = skill_path.parent
        relative_skill_path = str(skill_path.relative_to(root))
        records.append(
            InstalledSkillRecord(
                package_id=f"pkg.{package_dir.name}",
                skill_id=definition.id,
                source_ref=f"local://skills/{package_dir.name}",
                checksum=_directory_checksum(package_dir),
                root=str(root),
                skill_path=relative_skill_path,
                trusted=definition.trusted,
                risk_level=definition.risk_level,
                audit_ref=audit_ref,
                modified_ns=skill_path.stat().st_mtime_ns,
            )
        )
    return records


def _directory_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(file for file in path.rglob("*") if file.is_file()):
        digest.update(str(item.relative_to(path)).replace("\\", "/").encode("utf-8"))
        digest.update(item.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _record_params(record: InstalledSkillRecord) -> tuple[
    str,
    str,
    str,
    str,
    str,
    str,
    int,
    str,
    str | None,
    int,
]:
    return (
        record.package_id,
        record.skill_id,
        record.source_ref,
        record.checksum,
        record.root,
        record.skill_path,
        int(record.trusted),
        record.risk_level,
        record.audit_ref,
        record.modified_ns,
    )


def _record_from_row(row: sqlite3.Row) -> InstalledSkillRecord:
    return InstalledSkillRecord(
        package_id=str(row["package_id"]),
        skill_id=str(row["skill_id"]),
        source_ref=str(row["source_ref"]),
        checksum=str(row["checksum"]),
        root=str(row["root"]),
        skill_path=str(row["skill_path"]),
        trusted=bool(row["trusted"]),
        risk_level=str(row["risk_level"]),
        audit_ref=str(row["audit_ref"]) if row["audit_ref"] is not None else None,
        modified_ns=int(row["modified_ns"]),
    )
