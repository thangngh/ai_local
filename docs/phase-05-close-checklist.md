# Phase 05 Close Checklist

## Close Scope

Phase 5 can close when knowledge and memory boundaries stay explicit together:

- knowledge claims preserve source refs, level, rank, evidence strength,
  conflict state, and noise state
- evidence rank refuses unsafe authority inflation
- unresolved claim conflict does not become project truth
- memory writes stay explicit by layer, scope, confirmation, and sensitivity
- memory retrieval rejects stale, conflicted, wrong-scope, or laundered matches
- SQL schema and regression gates keep evidence, conflicts, updates, usage, and
  nonlinear state behavior visible

## Phase Gates

Run the Phase 5 focused gate surface:

```powershell
.\.venv\Scripts\python -m ai_local.cli knowledge
.\.venv\Scripts\python -m ai_local.cli evidence-rank
.\.venv\Scripts\python -m ai_local.cli multi-conflict --max-level hard
.\.venv\Scripts\python -m ai_local.cli memory-layers
.\.venv\Scripts\python -m ai_local.cli memory-sql
.\.venv\Scripts\python -m ai_local.cli memory-governance
.\.venv\Scripts\python -m ai_local.cli memory-regression
```

Run the cross-phase gates that Phase 5 can affect:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval --max-level hard
.\.venv\Scripts\python -m ai_local.cli flow-memory-rating --max-level hard
.\.venv\Scripts\python -m ai_local.cli evaluation
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli global-developer
.\.venv\Scripts\python -m ai_local.cli developer-sprints
```

## Regression Gates

Use the same close regression standard as earlier phases:

```powershell
.\.venv\Scripts\python -m pytest tests\harness
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check ai_local tests
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m ai_local.cli promote
```

## Close Decision

Close Phase 5 only when:

1. `F-KNOW-001` and `F-KNOW-002` focused gates pass together.
2. Retrieval, evaluator, lifecycle, and flow-memory gates show no false fact
   promotion across the Phase 2 and Phase 4 boundaries.
3. The close report records evidence for knowledge conflicts, memory conflict
   rejection, docs-match regression, and schema contract checks.
4. Full harness, pytest, lint, type, and promotion regression pass.

## Next Phase Handoff

Phase 6 should consume Phase 5 knowledge and memory decisions through explicit
evidence and permission contracts. Skill workflows should not grant authority to
claims or memories that Phase 5 gates would verify, quarantine, ask about, or
reject.
