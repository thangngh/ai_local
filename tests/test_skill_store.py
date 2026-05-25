from pathlib import Path

from typer.testing import CliRunner

from ai_local.cli import app
from ai_local.skills.store import (
    InstalledSkillRecord,
    InstalledSkillStore,
    cleanup_stale_installed_skills,
    refresh_installed_skill_registry,
)


def _write_installed_skill(root: Path, name: str, *, body: str = "Body") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: Installed skill\n"
        "trusted: true\n"
        "risk_level: low\n"
        "allowed_tools:\n"
        "- requirements.read\n"
        "---\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return skill_dir


def test_installed_skill_store_upserts_and_reports_stats(tmp_path: Path) -> None:
    store = InstalledSkillStore(tmp_path / "metadata.db")
    store.initialize()
    store.upsert(
        InstalledSkillRecord(
            package_id="pkg.simple-workflow",
            skill_id="simple-workflow",
            source_ref="local://skills/simple-workflow",
            checksum="sha256:abc",
            root=str(tmp_path / "skills"),
            skill_path="simple-workflow/SKILL.md",
            trusted=True,
            risk_level="low",
            audit_ref="audit-1",
            modified_ns=1,
        )
    )

    record = store.manifest()["pkg.simple-workflow"]

    assert record.skill_id == "simple-workflow"
    assert record.audit_ref == "audit-1"
    assert store.stats().packages == 1
    assert store.stats().trusted == 1


def test_refresh_installed_skill_registry_indexes_changes_and_deletes_removed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "skills"
    _write_installed_skill(root, "simple-workflow", body="old")
    store = InstalledSkillStore(tmp_path / "metadata.db")

    first = refresh_installed_skill_registry(root, store, audit_ref="install-audit-1")
    second = refresh_installed_skill_registry(root, store, audit_ref="install-audit-1")
    (root / "simple-workflow" / "SKILL.md").write_text(
        "---\n"
        "name: simple-workflow\n"
        "description: Installed skill\n"
        "trusted: true\n"
        "risk_level: low\n"
        "allowed_tools:\n"
        "- requirements.read\n"
        "---\n"
        "new\n",
        encoding="utf-8",
    )
    third = refresh_installed_skill_registry(root, store, audit_ref="install-audit-2")
    updated_audit_ref = store.manifest()["pkg.simple-workflow"].audit_ref
    (root / "simple-workflow" / "SKILL.md").unlink()
    fourth = refresh_installed_skill_registry(root, store)

    assert [record.package_id for record in first.upserted] == ["pkg.simple-workflow"]
    assert second.unchanged == ["pkg.simple-workflow"]
    assert [record.package_id for record in third.upserted] == ["pkg.simple-workflow"]
    assert updated_audit_ref == "install-audit-2"
    assert fourth.deleted == ["pkg.simple-workflow"]
    assert store.list_records() == []


def test_cleanup_stale_installed_skills_removes_missing_disk_rows(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    skill_dir = _write_installed_skill(root, "simple-workflow")
    store = InstalledSkillStore(tmp_path / "metadata.db")
    refresh_installed_skill_registry(root, store)
    (skill_dir / "SKILL.md").unlink()

    deleted = cleanup_stale_installed_skills(root, store)

    assert deleted == ["pkg.simple-workflow"]
    assert store.stats(root=root).packages == 0


def test_skill_registry_cli_refresh_stats_and_cleanup(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    db_path = tmp_path / "metadata.db"
    skill_dir = _write_installed_skill(root, "simple-workflow")
    runner = CliRunner()

    refresh = runner.invoke(
        app,
        [
            "skill-registry-refresh",
            "--root",
            str(root),
            "--metadata-db",
            str(db_path),
            "--audit-ref",
            "audit-1",
        ],
    )
    stats = runner.invoke(
        app,
        ["skill-registry-stats", "--root", str(root), "--metadata-db", str(db_path)],
    )
    (skill_dir / "SKILL.md").unlink()
    cleanup = runner.invoke(
        app,
        ["skill-registry-cleanup", "--root", str(root), "--metadata-db", str(db_path)],
    )

    assert refresh.exit_code == 0
    assert "upserted=1" in refresh.output
    assert stats.exit_code == 0
    assert "packages=1" in stats.output
    assert cleanup.exit_code == 0
    assert "deleted=1" in cleanup.output
