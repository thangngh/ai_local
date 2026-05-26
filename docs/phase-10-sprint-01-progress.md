# Phase 10 Sprint 01 Progress

Implemented Phase 10 Sprint 01: persistent runtime stores.

## Functional Scope

Phase 10 begins production hardening. Sprint 01 keeps the in-memory stores for
tests and simple flows, but adds SQLite-backed runtime stores with compatible
method contracts:

- `SQLiteAuditStore`
- `SQLiteAgentRunStore`
- `SQLiteQueueStore`

The agent loop and queue worker now consume store protocols rather than only
the in-memory implementations.

## Runtime Store Coverage

| Store | SQLite DB | Coverage |
| --- | --- | --- |
| Audit events | `audit.db` | Append/list/count persisted events |
| Agent runs | `tasks.db` | Create/get/mark planned/waiting/stopped/running/succeeded |
| Queue jobs | `tasks.db` | Enqueue/claim/run/fail/retry/dead-letter/list/status counts |

## CLI

```powershell
.\.venv\Scripts\python -m ai_local.cli runtime-store-stats `
  --tasks-db tasks.db `
  --audit-db audit.db
```

Output:

```text
RUNTIME_AUDIT events=<count>
RUNTIME_QUEUE pending=<count> ...
RUNTIME_AGENT_RUNS pending=<count> ...
```

## Gate Harness

Focused gate:

```powershell
.\.venv\Scripts\python -m pytest tests/test_persistent_runtime_stores.py
```

Related runtime gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli operational-safety
.\.venv\Scripts\python -m ai_local.cli thread-control
```

## Assessment

Sprint 01 moves the runtime from memory-only foundations toward a production
shape while keeping the existing behavior stable. The remaining production work
is schema versioning/migrations, crash recovery semantics, and TUI integration
on top of these persistent stores.
