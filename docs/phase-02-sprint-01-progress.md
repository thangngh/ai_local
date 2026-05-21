# Phase 02 Sprint 01 Progress

Sprint focus:

- `F-RET-001`: retrieval query handling and context packaging

## Functional `F-RET-001`

Before gate summary:

Phase 2 starts by tightening retrieval context packaging before storage engines
become durable. Query aliases and ranked chunk scores already exist; the sprint
adds the package boundary that preserves source references, content hashes,
selected evidence, rejected evidence, and safety decisions for noisy retrieval
paths.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli flow-memory-rating --max-level hard
```

After gate summary:

Retrieval and flow-memory gates passed. Runtime context packages now retain
source refs and content hashes, split selected evidence from rejected hits,
avoid packing prompt-injected or deep-shadowing hits, and preserve verify,
ask-user, quarantine, and stop paths before downstream evidence or decision
logic can use retrieved content.

## Sprint Exit

Phase 2 Sprint 01 retrieval baseline is present:

- Bilingual/noisy queries still normalize into alias search terms.
- Ranked hits keep flow, evidence, freshness, authority, interference, source
  reference, and content hash signals.
- Context packages expose selected and rejected hits with evidence refs.
- Deep retrieval safety flags stop policy shadowing and ask for review when a
  long retrieval chain is not decision-safe.

Phase 2 Sprint 02 can deepen indexer inputs and retrieval storage integration
without changing this context package contract.
