# Sprint 06 Progress

Sprint focus:

- `F-KNOW-001`: knowledge cards, evidence rank, and conflict resolver

## Functional `F-KNOW-001`

Before gate summary:

Sprint 06 turns knowledge harness rules into runtime claim decisions. A knowledge
claim must keep level, evidence strength, confidence, rank, conflict score, and
noise state visible before it can be used. Evidence ranking must apply authority,
freshness, relevance, confirmation, conflict, and staleness weights without
allowing prompt injection or laundered policy to inflate rank.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli knowledge
.\.venv\Scripts\python -m ai_local.cli evidence-rank
.\.venv\Scripts\python -m ai_local.cli multi-conflict --max-level hard
```

After gate summary:

Knowledge, evidence-rank, and multi-conflict focused gates passed. Runtime
knowledge policy now chooses use, verify-more, ask-user, quarantine, and reject
paths from explicit claim evidence. Evidence rank returns canonical, strong,
caution, weak, or reject bands, and conflict resolution preserves unresolved
ties, missing-test-evidence deferrals, and no-safe-path stops.

## Sprint 06 Exit

Sprint 06 knowledge runtime baseline is present:

- Knowledge items carry level, source, confidence, rank, evidence strength,
  conflict score, and noise state.
- Knowledge policy follows claim rank, evidence, conflict, and hard-reject
  boundaries from the gate harness.
- Evidence signals apply the rank formula and hard reject unsafe evidence noise.
- Multi-instance conflict decisions separate ask-user, defer-until-evidence,
  and stop paths without inventing a winner.

Sprint 07 can extend the knowledge baseline into memory layers, schema,
regression, and governance scoring.
