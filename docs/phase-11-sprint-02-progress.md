# Phase 11 Sprint 02 Progress

Sprint 02 adds audited queue operation controls for the local operator workflow.

## Functional Scope

- `ai_local.queue.operations` provides operator-safe queue actions:
  - list queue jobs
  - retry `dead_letter` jobs back to `pending`
  - cancel `pending` or `claimed` jobs
- Every retry/cancel decision writes an audit event.
- Unsafe transitions fail closed:
  - retry only accepts `dead_letter`
  - cancel only accepts `pending` or `claimed`
  - missing jobs are denied
  - unsupported queue schema is denied before mutation
- CLI commands:
  - `queue-jobs`
  - `queue-retry <job_id>`
  - `queue-cancel <job_id>`
- `phase-fast-gate` now includes `phase11_queue_operations`.

## Gate Harness

Focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_queue_operations.py tests/test_runtime_tui.py tests/harness/test_phase_fast_gate.py
```

Combined gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli thread-control --max-level hard
.\.venv\Scripts\python -m ai_local.cli phase-fast-gate --output .reports\phase11-sprint02\phase-fast-gate.json
```

Quality gates:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m pytest
```

## Run Summary

- Focused tests: `12 passed`
- Fast gate: `23/23 passed`
- Fast gate report: `.reports\phase11-sprint02\phase-fast-gate.json`
- `operational-safety --max-level hard`: passed through hard, max hop depth 30
- `thread-control --max-level hard`: passed through hard, max hop depth 30
- `ruff check .`: passed
- `mypy ai_local tests`: passed, 194 source files
- Full pytest: `304 passed, 1 skipped`

Pytest still reports the local `.pytest_cache` permission warning; this is a
cache write issue only.
