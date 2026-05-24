# Phase 05 Sprint 01 Progress

Sprint focus:

- `F-KNOW-001`: knowledge claims, evidence rank, and conflict resolution

## Functional `F-KNOW-001`

Before gate summary:

Phase 5 Sprint 01 touches the knowledge claim runtime, evidence ranker,
conflict resolver, and in-memory knowledge lookup helpers. It does not require
Docker or an external service because the current project persistence boundary
is local SQLite and the focused sprint gates run in-process.

Gate commands:

```powershell
python -m ai_local.cli knowledge
python -m ai_local.cli evidence-rank
python -m ai_local.cli multi-conflict --max-level hard
```

After gate summary:

Knowledge claims now preserve explicit source references, evidence references,
and provenance while retaining the previous `source_ref` compatibility field.
High-rank claims require evidence references before they can be used, current
claims require a fresh source reference, and policy laundering still rejects
before lower-priority scoring rules. Evidence ranking caps authority inflation
from unknown sources and noisy comments before applying the existing rank
formula. Conflict resolution keeps tie paths user-routed, defers missing test
evidence, stops unsafe paths, and selects a low-risk winner only when evidence
rank separation is material.

## Sprint Exit

- Project/current/policy claims keep source and evidence refs explicit.
- Unknown-source authority cannot become canonical through rank inflation.
- Equal or unsafe conflicts do not become false facts.
- Clear low-risk evidence winners can be selected without widening Phase 4
  evaluator routing.
