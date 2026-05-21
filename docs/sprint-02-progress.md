# Sprint 02 Progress

Sprint focus:

- `F-CORE-003`: Tool registry and allowed tool execution
- `F-CORE-004`: Queue worker, thread control, and outbox dispatcher

## Functional `F-CORE-003`

Before gate summary:

Sprint 02 adds an execution boundary around registered tools. The patch keeps
tool definitions in the existing YAML registry, normalizes tool calls/results,
checks approval/provider/secret-path policy before handler execution, and writes
audit-ready results without making web retrieval authoritative.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level medium
.\.venv\Scripts\python -m ai_local.cli prompt-injection --max-level medium
```

After gate summary:

Tool-combo and prompt-injection focused gates passed. Registered handler calls
return normalized results, unknown tools and unsupported web providers are
denied, secret-like path arguments are blocked, and audited definitions create
audit events when an audit store is present.

## Functional `F-CORE-004`

Before gate summary:

Runtime control needs computation and side effects to separate before durable
storage lands. The patch extends the in-memory queue lifecycle, runs `agent_run`
jobs through a worker handler, protects one project write owner at a time, and
dispatches approved outbox events with idempotency and audit results.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli thread-control
.\.venv\Scripts\python -m ai_local.cli operational-safety
```

After gate summary:

Thread-control and operational-safety focused gates passed through extreme
coverage. Worker jobs move through running/succeeded/retry/dead-letter paths,
project write locks return an explicit wait decision for a competing run, outbox
events hold approval-gated side effects, and duplicate idempotency keys dispatch
once.

## Sprint 02 Exit

Sprint 02 MVP runtime control is present:

- Tool execution is registry-driven and policy checked before handler execution.
- Tool results and audit events have normalized in-memory contracts.
- Queue workers can drive an `agent_run` into the Sprint 01 loop.
- Thread control enforces the per-project write-run boundary.
- Outbox dispatch holds approval-required events and prevents duplicate effects.

Sprint 03 can build retrieval and indexer inputs on top of these runtime
boundaries without treating untrusted tool output as direct policy.
