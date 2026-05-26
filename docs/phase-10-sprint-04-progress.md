# Phase 10 Sprint 04 Progress

Sprint 04 adds a TUI-ready runtime control-plane snapshot. It does not introduce
an interactive UI dependency yet; instead it creates a stable data and text
surface that a later terminal UI can render without reading SQLite tables
directly.

## Functional Scope

- `ai_local.runtime.control_plane` builds a single runtime snapshot from:
  - SQLite queue job counts
  - SQLite agent run counts
  - SQLite audit event count and recent audit events
  - runtime schema versions
- The snapshot classifies health as `ok`, `warn`, or `critical`.
- Critical issues are raised for dead-letter queue jobs or missing/wrong schema
  versions.
- Warning issues are raised for failed or user-waiting agent runs.
- `runtime-control-panel` renders the snapshot as deterministic terminal text
  and can return a non-zero exit code when `--fail-on-critical` is enabled.

## Gate Harness

Focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_runtime_control_plane.py tests/test_persistent_runtime_stores.py tests/test_runtime_schema_versions.py
```

Combined gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli thread-control --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli request-lifecycle --max-level hard
```

Quality gates:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m pytest
```

## Run Summary

- Focused tests: `11 passed`
- `thread-control --max-level hard`: passed through hard, max hop depth 30
- `operational-safety --max-level hard`: passed through hard, max hop depth 30
- `request-lifecycle --max-level hard`: passed through hard, max hop depth 30
- `runtime-control-panel` smoke run: rendered `health=ok` on empty runtime DBs
- `ruff check .`: passed
- `mypy ai_local tests`: passed, 188 source files
- Full pytest: `292 passed, 1 skipped`

Pytest still reports the local `.pytest_cache` permission warning; this is a
cache write issue only.
