# Phase 05 Sprint 02 Progress

Sprint focus:

- `F-KNOW-002`: memory layers, SQL contract, governance, and regression

## Functional `F-KNOW-002`

Before gate summary:

Sprint 02 touches memory write policy, retrieval policy, schema contract,
runtime memory records, and nonlinear regression behavior. The patch keeps the
local-first boundary: no Docker service is required because memory persistence
contracts are represented by local schema definitions and in-process policy
gates.

Gate commands:

```powershell
python -m ai_local.cli memory-layers
python -m ai_local.cli memory-sql
python -m ai_local.cli memory-governance
python -m ai_local.cli memory-regression
```

After gate summary:

Memory items now carry explicit evidence refs, conflict refs, role, sensitivity,
confirmation owner, source hash, and usage metadata. Write policy rejects secret
memory, asks before sensitive unconfirmed memory, and verifies any memory write
without explicit evidence. Retrieval policy drops wrong-scope and wrong-role
matches, blocks inactive records, verifies unconfirmed sensitive or unevidenced
memory, and preserves existing demotion, archive, and conflict behavior. The
schema contract records source hash, role, sensitivity, and confirmation owner.
Regression now verifies instead of restoring when required constraints are not
fully restored.

## Sprint Exit

- Memory writes remain explicit by evidence, confirmation, sensitivity, layer,
  and scope.
- Retrieval rejects stale, conflicted, wrong-scope, wrong-role, inactive, or
  unevidenced matches before context injection.
- Runtime records expose evidence, conflict, and usage history for audit.
- Nonlinear memory restoration refuses partial constraint restoration.
