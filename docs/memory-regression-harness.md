# Memory Regression Harness

This harness tests nonlinear memory behavior before patches that touch memory, retrieval, context packing, or evaluator logic.

It focuses on three risks:

- nonlinear state flow: conversation/task state is not a simple list
- regression: the agent must restore an earlier state after interruptions
- docs match: memory must match source documents, evidence, role, scope, and flow before use

## Promotion Levels

### Easy

Direct docs-match and one-hop state return.

Example:

```text
a-b-a
```

The active state must return to `a`.

### Medium

Branching state with an interrupt.

Example:

```text
a-b-c-d-c
```

The active state must restore `c`, not stay in interrupting state `d`.

### Hard

Multi-branch regression with negative constraints and conflicting memory candidates.

Example:

```text
a-b-c-b-c-d-a
```

The active state must restore `a`, while rejecting wrong-role memory.

### Extreme

Deep nonlinear regression with laundered docs-match or recursive state shadowing.

Example:

```text
a-b-c-d-e-b-c-f-a
```

The active state must restore `a` after multiple interrupts.

## Docs Match

Docs match is not semantic similarity alone.

```text
doc_match =
  0.30 * semantic_match
+ 0.25 * flow_match
+ 0.20 * evidence_match
+ 0.15 * scope_match
- 0.10 * interference
```

Required fields:

- `source_ref`
- `evidence`
- `flow`
- `scope`
- `role`
- `status`

## Regression Score

```text
RegressionAccuracy = constraints_restored_correctly / constraints_required
```

Required state fields:

- `active_state`
- `state_distribution`
- `active_constraints`
- `retrieved_memories`
- `rejected_memories`
- `new_evidence`

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-regression
```

Stop at a level:

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-regression --max-level hard
```

