# Phase 03 Sprint 04 Progress

Sprint focus:

- `F-HAR-007`: post-apply patch stage trace
- `F-HAR-008`: Big Harness safety and confirmation policy contract

## Functional `F-HAR-007`

Before gate summary:

Sprint 03 proved all pre-apply stages before a patch was accepted, but a runtime
attempt could still present passing focused checks and evaluator evidence
without a matching post-apply trace through test and evaluator stages.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli small-patch
.\.venv\Scripts\python -m ai_local.cli composite
```

After gate summary:

Accepted patch attempts now prove `RUN_FOCUSED_TESTS`, `TEST_GATE`, and
`PATCH_EVALUATOR` after `APPLY_PATCH`. Missing or late test stages return to
focused tests; missing evaluator stage returns to patch evaluation.

## Functional `F-HAR-008`

Before gate summary:

`configs/big_harness.yaml` already declared safety and confirmation policy for
whole-run patch control, but the runtime loader only validated limits and core
gate names.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli big-harness
.\.venv\Scripts\python -m ai_local.cli patch-levels
.\.venv\Scripts\python -m ai_local.cli promote
```

After gate summary:

Big Harness policy now loads and validates diff-before-write, destructive-shell
blocking, code-test requirement, rollback-on-failed-gate, retrieved-content
data-only behavior, risk thresholds, and confirmation requirements for public
API, schema, and security-sensitive changes.

## Sprint Exit

- Patch runtime traces pre-apply and post-apply required stages in order.
- Passing checks and evaluator evidence must have matching stage completion.
- Big Harness safety declarations are executable config contract, not unused
  YAML fields.
- Whole-run confirmation controls stay aligned with patch-level risk gates.
