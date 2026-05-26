# Phase 11 Sprint 03 Progress

Sprint 03 adds audited agent run operation controls for the local operator
workflow.

## Functional Scope

- `ai_local.agent.operations` provides operator-safe agent run actions:
  - list agent runs
  - stop `pending`, `planned`, `waiting_user`, or `running` runs
  - cancel `pending`, `planned`, or `waiting_user` runs
- Every stop/cancel decision writes an audit event.
- Unsafe transitions fail closed:
  - terminal runs cannot be cancelled or stopped
  - missing runs are denied
  - unsupported agent run schema is denied before mutation
- CLI commands:
  - `agent-runs`
  - `agent-run-stop <run_id>`
  - `agent-run-cancel <run_id>`
- `phase-fast-gate` now includes `phase11_agent_run_operations`.

## Gate Harness

Focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_agent_operations.py tests/test_runtime_control_plane.py tests/harness/test_phase_fast_gate.py
```

Combined gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level hard
.\.venv\Scripts\python -m ai_local.cli request-lifecycle --max-level hard
.\.venv\Scripts\python -m ai_local.cli phase-fast-gate --output .reports\phase11-sprint03\phase-fast-gate.json
```

Quality gates:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m pytest
```

## Run Summary

- Focused tests: `13 passed`
- Fast gate: `24/24 passed`
- Fast gate report: `.reports\phase11-sprint03\phase-fast-gate.json`
- `agent-loop --max-level hard`: passed through hard, max hop depth 25
- `request-lifecycle --max-level hard`: passed through hard, max hop depth 30
- `ruff check .`: passed
- `mypy ai_local tests`: passed, 196 source files
- Full pytest: `308 passed, 1 skipped`

Pytest still reports the local `.pytest_cache` permission warning; this is a
cache write issue only.
