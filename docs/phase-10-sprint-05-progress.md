# Phase 10 Sprint 05 Progress

Sprint 05 adds a fast gate aggregator for the current Phase 1 through Phase 10
surface. The goal is to give the project a single quick command that exercises
the high-signal harnesses without spawning every CLI gate as a separate process.

## Functional Scope

- `configs/phase_fast_gates.yaml` defines the current cross-phase fast gate set.
- `ai_local.harness.phase_fast_gate` loads the gate matrix and runs each gate
  directly through Python harness functions.
- The matrix covers:
  - core loop and request lifecycle
  - retrieval and memory SQL
  - patch pipeline and conflict routing
  - evaluation, confirmation, knowledge, evidence rank
  - tools, prompt-injection, skills, memory governance
  - operational safety, thread control
  - Phase 9 integrated close replay/stress
  - Phase 10 runtime store, schema, sandbox, and control-panel smoke gates
- `phase-fast-gate` exposes the aggregate runner through the CLI.

## Gate Harness

Sprint focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/harness/test_phase_fast_gate.py
```

Full fast gate:

```powershell
.\.venv\Scripts\python -m ai_local.cli phase-fast-gate
```

Quality gates:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m pytest
```

## Run Summary

- Focused tests: `4 passed`
- Full fast gate Phase 1 through Phase 10 current: `21/21 passed`
- Phase 9 integrated close inside fast gate: replay `3/3`, stress `3/3`
- Phase 10 smoke gates inside fast gate:
  - runtime stores: passed
  - runtime schema versions: passed
  - tool sandbox: passed
  - runtime control panel: passed
- `ruff check .`: passed
- `mypy ai_local tests`: passed, 190 source files
- Full pytest: `296 passed, 1 skipped`

Pytest still reports the local `.pytest_cache` permission warning; this is a
cache write issue only.
