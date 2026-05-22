# Phase 03 Sprint 02 Progress

Sprint focus:

- `F-HAR-003`: patch evidence refs by evidence kind
- `F-HAR-004`: focused check result evidence binding

## Functional `F-HAR-003`

Before gate summary:

Sprint 01 required evidence refs but left all refs as untyped strings. Phase 3
needs the policy to distinguish retrieved context, git diff, test, and manual
evidence so required evidence cannot be satisfied by an unrelated string.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli small-patch
.\.venv\Scripts\python -m ai_local.cli patch-levels
.\.venv\Scripts\python -m ai_local.cli patch-pipeline --max-level hard
```

After gate summary:

Patch evidence refs now carry `context`, `diff`, `test`, or `manual` kinds.
Hard-level `git_diff` evidence requires a diff ref, and focused harness evidence
requires a test ref before the policy can continue.

## Functional `F-HAR-004`

Before gate summary:

The patch pipeline carried focused check results, but a caller could pass a
successful attempt without a result for each required check or with a result
that had no test evidence.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli composite
.\.venv\Scripts\python -m ai_local.cli conflict-paths --max-level hard
```

After gate summary:

Required check IDs must have explicit `PatchCheckResult` rows and passing
required checks must carry test evidence refs. Missing result or missing test
evidence returns the attempt to `RUN_FOCUSED_TESTS`; existing failed-check retry
and serious-failure rollback branches remain unchanged.

## Sprint Exit

- Patch evidence refs are typed by evidence source.
- Hard policy paths require diff and focused-test evidence kinds.
- Required focused checks bind runtime result rows to the harness check IDs.
- Passing required checks cannot reach the decision gate without test evidence.
