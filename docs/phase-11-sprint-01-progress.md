# Phase 11 Sprint 01 Progress

Sprint 01 starts the TUI-first operations layer. It adds a deterministic runtime
operator frame that consumes the structured Phase 10 runtime control snapshot.

## Functional Scope

- `ai_local.runtime.tui` renders an operator-facing runtime frame.
- The frame includes:
  - runtime health
  - queue counts
  - agent run counts
  - schema versions
  - audit event count and recent audit entries
  - runtime issues
- `runtime-tui` exposes the frame through CLI with finite `--iterations` and
  `--refresh-seconds` options for testable refresh behavior.
- `phase-fast-gate` now includes a Phase 11 `runtime_tui_smoke` gate and updates
  its source reference to `phase_1_to_phase_11_current`.

## Gate Harness

Focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_runtime_tui.py tests/test_runtime_control_plane.py tests/harness/test_phase_fast_gate.py
```

Phase gate:

```powershell
.\.venv\Scripts\python -m ai_local.cli phase-fast-gate --output .reports\phase11-sprint01\phase-fast-gate.json
```

Quality gates:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m pytest
```

## Run Summary

- Focused tests: `12 passed`
- Fast gate: `22/22 passed`
- Fast gate report: `.reports\phase11-sprint01\phase-fast-gate.json`
- `ruff check .`: passed
- `mypy ai_local tests`: passed, 192 source files
- Full pytest: `300 passed, 1 skipped`

Pytest still reports the local `.pytest_cache` permission warning; this is a
cache write issue only.
