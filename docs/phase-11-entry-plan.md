# Phase 11 Entry Plan

Phase 11 should turn the Phase 10 operator surfaces into an actual local runtime
operator workflow.

## Objective

Build a TUI-first operations layer for running, observing, and recovering the
local AI runtime without introducing a web UI dependency.

## Sprint Plan

| Sprint | Functional Target | Gate Harness |
| --- | --- | --- |
| Sprint 01 | Interactive TUI shell for runtime control snapshot: status, queue counts, agent runs, schema versions, recent audit events. | `runtime_control_panel`, `phase-fast-gate`, full pytest focused on runtime control. |
| Sprint 02 | Queue operation controls: inspect jobs, retry dead letters, mark/cancel safe states with audit evidence. | `operational-safety --max-level hard`, `thread-control --max-level hard`, new queue operation tests. |
| Sprint 03 | Agent run operation controls: inspect run state, stop/cancel waiting/running paths, preserve audit trail. | `agent-loop --max-level hard`, `request-lifecycle --max-level hard`, runtime control tests. |
| Sprint 04 | Backup and restore for runtime SQLite DBs with schema version checks. | `memory-sql --max-level hard`, `operational-safety --max-level hard`, new backup/restore tests. |
| Sprint 05 | Sandbox backend planning: explicit Docker/bubblewrap adapter config, still fail-closed when unavailable. | `tool-combo --max-level hard`, `prompt-injection --max-level hard`, sandbox tests. |
| Sprint 06 | Phase 11 close runner: combine TUI/control, queue recovery, backup/restore, sandbox, and Phase 1-11 fast gate reports. | `phase-fast-gate`, full pytest, ruff, mypy, close report artifact. |

## Functional Requirements

- TUI must consume structured runtime snapshots, not parse ad hoc SQLite tables.
- Every operator action must write audit evidence.
- Unsafe operator actions must fail closed or require explicit confirmation.
- Runtime DB operations must check schema versions before mutation.
- Queue and agent recovery paths must be reversible or at least evidence-rich.
- Fast gate reports must remain machine-readable artifacts.

## Non-Functional Requirements

- Keep the runtime local-first.
- Keep terminal output deterministic enough for tests.
- Keep dependencies conservative; add a TUI dependency only if it materially
  improves operator ergonomics.
- Preserve Windows compatibility for PowerShell workflows.
- Maintain full `ruff`, `mypy`, and `pytest` gates.

## Entry Gate

Before Sprint 01 starts:

```powershell
.\.venv\Scripts\python -m ai_local.cli phase-fast-gate `
  --output .reports\phase11-entry\phase-fast-gate.json
.\.venv\Scripts\python -m pytest tests/test_runtime_control_plane.py
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
```

