# Phase 11 Sprint 04 Progress

Sprint 04 adds runtime SQLite backup and restore controls with schema version
checks.

## Functional Scope

- `ai_local.runtime.backup` creates directory-based runtime backup artifacts:
  - `tasks.db`
  - `audit.db`
  - `manifest.json`
- Restore validates the backup manifest and source DB schema versions before
  replacing target runtime DBs.
- Restore fails closed when a backup DB has unsupported schema versions.
- CLI commands:
  - `runtime-backup <backup_dir>`
  - `runtime-restore <backup_dir>`
- `phase-fast-gate` now includes `phase11_runtime_backup_restore`.

## Gate Harness

Focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_runtime_backup.py tests/test_runtime_schema_versions.py tests/harness/test_phase_fast_gate.py
```

Combined gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli phase-fast-gate --output .reports\phase11-sprint04\phase-fast-gate.json
```

Quality gates:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m pytest
```

## Run Summary

- Focused tests: `12 passed`
- Fast gate: `25/25 passed`
- Fast gate report: `.reports\phase11-sprint04\phase-fast-gate.json`
- `memory-sql --max-level hard`: passed through hard, max hop depth 25
- `operational-safety --max-level hard`: passed through hard, max hop depth 30
- `ruff check .`: passed
- `mypy ai_local tests`: passed, 198 source files
- Full pytest: `312 passed, 1 skipped`

Pytest still reports the local `.pytest_cache` permission warning; this is a
cache write issue only.
