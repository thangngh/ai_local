# Sprint 04 Progress

Sprint focus:

- `F-HAR-001`: Big harness and small patch harness
- `F-HAR-002`: Patch pipeline with evidence and rollback decisions

## Functional `F-HAR-001`

Before gate summary:

Sprint 04 turns patch policy into a runtime contract. A patch harness spec names
the requirement, objective, allowed files, evidence, checks, and rollback plan;
the policy compares a concrete change summary against patch level limits before
the pipeline can call it safe.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli big-harness
.\.venv\Scripts\python -m ai_local.cli small-patch
.\.venv\Scripts\python -m ai_local.cli patch-levels
```

After gate summary:

Big, small, and patch-level focused gates passed. Runtime patch policy accepts
scoped evidence-complete patches, splits over-limit change summaries, requests
confirmation when risk exceeds the selected level, and rejects missing scope,
evidence, checks, or rollback data.

## Functional `F-HAR-002`

Before gate summary:

The patch pipeline runtime must preserve stage decisions after the policy layer
passes. A patch attempt carries context readiness, semantic review status,
focused check results, and whether more patch work remains so retry and rollback
branches are explicit rather than inferred from prose.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli composite
.\.venv\Scripts\python -m ai_local.cli conflict-paths --max-level hard
```

After gate summary:

Patch pipeline, composite, and conflict focused gates passed. Runtime attempt
decisions now cover retrieve-more, split, ask-user, retry, rollback, accept, and
next-patch paths using policy results and check evidence.

## Sprint 04 Exit

Sprint 04 MVP harness execution baseline is present:

- Patch harness specs bind requirement, scope, evidence, checks, and rollback.
- Patch level limits drive split and confirmation decisions.
- Patch attempts preserve context, semantic review, focused checks, and decision
  reasons.
- Failed focused checks retry, serious failures rollback, and accepted patches
  can continue to a next patch.

Sprint 05 can add evaluator and confirmation implementation on top of patch
decisions that already carry evidence and risk boundaries.
