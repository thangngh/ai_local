# Sprint 07 Progress

Sprint focus:

- `F-KNOW-002`: memory layers, SQL schema contract, regression, and governance

## Functional `F-KNOW-002`

Before gate summary:

Sprint 07 turns memory gate rules into runtime write and retrieval decisions.
Memory must keep layer, scope, evidence, confirmation, freshness, conflict,
usage, source-change, and sensitivity signals visible before it is written or
injected. The schema contract must preserve evidence, conflict, update, and usage
tables so a later durable SQLite store can audit these decisions.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-layers
.\.venv\Scripts\python -m ai_local.cli memory-sql
.\.venv\Scripts\python -m ai_local.cli memory-governance
.\.venv\Scripts\python -m ai_local.cli memory-regression
```

After gate summary:

Memory layer, SQL, governance, and regression focused gates passed. Runtime
memory policy now rejects secret-like writes, asks for confirmation before
policy memory, verifies weak project evidence, drops wrong-scope retrieval,
demotes changed-source memory, blocks conflicted memory, quarantines deep
poisoning, and stops safety-policy laundering. Regression helpers keep docs
match and nonlinear state restoration explicit.

## Sprint 07 Exit

Sprint 07 memory runtime baseline is present:

- Layer policies cover `M0` through `M5` with scope, fact, evidence, and
  confirmation boundaries.
- Memory schema contract names item, evidence, conflict, update, and usage
  columns required by the SQL gate.
- Write and retrieval policies separate accept, verify, ask, drop, demote,
  quarantine, stop, inject, archive, and confirmed-precedence paths.
- Regression helpers score docs match and restore active state after nonlinear
  task interruptions while rejecting laundered matches.

Sprint 08 can integrate skill metadata and permission-aware workflow paths on
top of knowledge and memory policy that stay explicit.
