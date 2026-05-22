# Phase 03 Sprint 03 Progress

Sprint focus:

- `F-HAR-005`: pre-apply patch stage trace
- `F-HAR-006`: evaluator result evidence before decision

## Functional `F-HAR-005`

Before gate summary:

The patch pipeline config requires context, static diff, scope, patch-size,
risk, and semantic review gates before write application. Runtime patch
attempts still reached policy and focused-check decisions without proving that
those pre-apply stages were completed in the required order.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-pipeline --max-level hard
.\.venv\Scripts\python -m ai_local.cli small-patch
.\.venv\Scripts\python -m ai_local.cli conflict-paths --max-level hard
```

After gate summary:

Patch attempts now carry a completed stage trace. Missing or out-of-order
pre-apply stages return the attempt to patch proposal before an accepted patch
can claim the diff, scope, risk, and semantic review path.

## Functional `F-HAR-006`

Before gate summary:

Focused tests were bound to required check IDs in Sprint 02, but decision entry
still did not require a patch evaluator result with evidence.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli composite
.\.venv\Scripts\python -m ai_local.cli promote
```

After gate summary:

Patch attempts now carry evaluator status and evaluator evidence. Failed
evaluator results or evaluator evidence that is absent or not test/manual
evidence return to `PATCH_EVALUATOR` instead of reaching the decision gate.

## Sprint Exit

- Accepted patch attempts prove the configured pre-apply stage order.
- Static diff and scope gates cannot be represented after `APPLY_PATCH`.
- Focused check evidence remains required before evaluator handling.
- Evaluator result and evidence are bound before `DECISION_GATE`.
