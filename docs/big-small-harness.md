# Big Harness and Small Patch Harness

## Big Harness

The Big Harness controls a whole agent run:

- max steps
- max tool calls
- retry budget
- hop-depth limit
- required gates
- safety and confirmation policies

Config:

- `configs/big_harness.yaml`

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli big-harness
```

## Small Patch Harness

The Small Patch Harness controls one patch at a time:

- files changed
- changed lines
- hop depth
- required evidence
- required checks
- hard rules for schema, dependency, public API, and rollback behavior

Config:

- `configs/small_patch_harness.yaml`

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli small-patch
```

## Rule

No production patch is valid until the small patch harness has:

- `requirement_id`
- focused harness evidence
- `test.harness` check
- allowed-file scope

