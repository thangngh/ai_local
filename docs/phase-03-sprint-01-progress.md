# Phase 03 Sprint 01 Progress

Sprint focus:

- `F-HAR-001`: patch harness runtime contract
- `F-HAR-002`: diff-derived scope and sizing gates

## Functional `F-HAR-001`

Before gate summary:

Phase 3 starts by tightening the patch contract that the existing small harness
already describes. The runtime policy had requirement, scope, evidence names,
checks, risk, and rollback fields, but did not require concrete evidence refs
for the patch being evaluated.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli big-harness
.\.venv\Scripts\python -m ai_local.cli small-patch
.\.venv\Scripts\python -m ai_local.cli patch-levels
```

After gate summary:

Patch harness specs now carry evidence refs alongside required evidence names.
Missing references reject a policy decision before patch apply paths can claim
focused context or checks.

## Functional `F-HAR-002`

Before gate summary:

Scope and size gates should evaluate a concrete diff shape instead of trusting
aggregate counts supplied by callers. Patch levels also already declare allowed
and forbidden change types, so policy must enforce those declarations.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-pipeline --max-level hard
.\.venv\Scripts\python -m ai_local.cli composite
.\.venv\Scripts\python -m ai_local.cli conflict-paths --max-level hard
```

After gate summary:

`PatchFileChange` produces diff-derived changed line, function, path, and change
type summaries. Patch policy rejects forbidden or out-of-level change types and
retains the existing split, ask-user, retry, rollback, and accept branches.

## Sprint Exit

- Harness policy binds requirement ID, allowed files, evidence names, evidence
  refs, checks, risk, and rollback state.
- Diff file changes derive patch size data for policy gates.
- Patch levels load allowed and forbidden change type declarations into runtime
  validation.
- Focused contract tests cover scoped acceptance, over-limit split, risky
  ask-user, missing evidence refs, and dependency-change rejection.
