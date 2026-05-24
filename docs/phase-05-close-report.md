# Phase 05 Close Report

## Close Scope

Phase 5 closes the local knowledge and memory boundary:

- knowledge claims preserve source refs, evidence refs, provenance, rank,
  evidence strength, conflict state, and noise state
- evidence rank prevents unsafe authority inflation and hard-rejects injection,
  policy laundering, and repeated untrusted claims
- conflict handling avoids false winners and selects a candidate only when
  evidence separation is material and risk is acceptable
- memory writes require explicit evidence, valid layer/scope, confirmation when
  required, and sensitivity checks
- memory retrieval rejects wrong-scope, wrong-role, stale, conflicted,
  inactive, sensitive-unconfirmed, or unevidenced matches before injection
- SQL schema and runtime records expose evidence, conflicts, updates, usage,
  source hash, role, sensitivity, and confirmation owner
- nonlinear memory regression refuses laundered or partial constraint restores
- knowledge-to-memory handoff blocks silent promotion of weak, conflicting,
  rejected, or quarantined claims

## Closure Gates

Phase close gates:

```powershell
python -m ai_local.cli knowledge
python -m ai_local.cli evidence-rank
python -m ai_local.cli multi-conflict --max-level hard
python -m ai_local.cli memory-layers
python -m ai_local.cli memory-sql
python -m ai_local.cli memory-governance
python -m ai_local.cli memory-regression
python -m ai_local.cli retrieval --max-level hard
python -m ai_local.cli flow-memory-rating --max-level hard
python -m ai_local.cli evaluation
python -m ai_local.cli request-lifecycle
python -m ai_local.cli global-developer
python -m ai_local.cli developer-sprints
```

Regression gates:

```powershell
python -m pytest tests\harness
python -m pytest
python -m ruff check ai_local tests
python -m mypy ai_local tests
python -m ai_local.cli promote
```

## Exit Decision

Phase 5 can close when the focused knowledge and memory gates, cross-phase
retrieval/evaluator/lifecycle gates, and full regression gates pass together.
Phase 6 should consume knowledge and memory decisions through explicit evidence
and permission contracts; skills must not grant authority to claims or memory
items that Phase 5 would verify, ask about, quarantine, reject, or drop.
