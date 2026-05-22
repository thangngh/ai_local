# Phase 03 Close Report

## Close Scope

Phase 3 closes the harness runtime layer for local patch work:

- Big Harness safety and confirmation policy
- Small Patch levels and allowed change boundaries
- Patch evidence refs, evidence kinds, and focused check evidence
- Diff-derived patch summary and change-type policy
- Pre-apply and post-apply stage trace
- Evaluator evidence before decision
- Retry budget ask/rollback routing

## Closure Gates

Phase close gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli big-harness
.\.venv\Scripts\python -m ai_local.cli small-patch
.\.venv\Scripts\python -m ai_local.cli patch-levels
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli composite
.\.venv\Scripts\python -m ai_local.cli conflict-paths
.\.venv\Scripts\python -m ai_local.cli global-developer
.\.venv\Scripts\python -m ai_local.cli developer-sprints
```

Full regression gates:

```powershell
.\.venv\Scripts\python -m pytest tests\harness
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m ai_local.cli promote
```

## Exit Decision

Phase 3 is closed when closure gates and full regression gates pass together.
The next phase should consume these patch constraints instead of widening them
while evaluation runtime behavior is being built.

## Phase 4 Entry

Phase 4 Sprint 01 should start from `F-EVAL-001`:

- evaluator score and reason schema
- decision routing for accept, retry, ask, verify, quarantine, and stop
- confirmation flow binding for risk, ambiguity, and protected actions
- evaluator/decision gate evidence that can be consumed by the closed patch
  pipeline contract
