# Phase 03 Sprint 05 Progress

Sprint focus:

- `F-HAR-003` to `F-HAR-008`: Phase 3 harness closure

## Functional `F-HAR-003`

Before gate summary:

Sprint 01 and Sprint 02 added evidence refs, evidence kinds, and focused check
evidence. The Phase 3 closure pass needed those contracts represented in the
developer functional inventory instead of only progress docs and unit tests.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli small-patch
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli patch-levels
```

After gate summary:

Developer harness coverage now includes the Phase 3 evidence binding functional.
Small-patch, patch-level, and runtime pipeline gates remain the closure checks
for evidence refs, evidence kinds, and focused check proof.

## Functional `F-HAR-004` to `F-HAR-008`

Before gate summary:

Sprint 03 and Sprint 04 bound pre-apply stages, post-apply stages, evaluator
evidence, and Big Harness safety policy. The remaining executable gap was the
Big Harness retry budget for repeated patch retry paths.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli big-harness
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli composite
.\.venv\Scripts\python -m ai_local.cli conflict-paths --max-level hard
```

After gate summary:

Developer harness coverage now carries the focused-check, pre-apply,
evaluator-evidence, post-apply, and Big Harness contract functionals. Patch
attempts carry a retry count and `decide_patch_attempt` accepts the Big Harness
retry limit. Exhausted retry before apply asks the user; exhausted retry after
an applied patch rolls back instead of retrying indefinitely.

## Sprint Exit

- Phase 3 closure functionals are represented in global and sprint developer
  harness metadata.
- Patch evidence binding, stage trace, evaluator evidence, and Big Harness
  safety rules remain covered by promotion gates.
- Retry budget is executable in patch runtime decision routing.
- Phase 3 is ready for close gates and full regression before Phase 4 work.
