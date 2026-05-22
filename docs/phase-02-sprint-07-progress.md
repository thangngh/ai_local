# Phase 02 Sprint 07 Progress

Sprint focus:

- `F-RET-007`: optional vector candidate boundary and Phase 2 exit review

## Functional `F-RET-007`

Before gate summary:

Phase 2 already has ripgrep exact matches, persisted FTS chunks, persisted code
symbols, and one context package path. Requirements also reserve vector search
for environments where a vector backend is available. The runtime still needed
a bounded vector candidate path that does not let speculative semantic hits
outrank exact lexical evidence for code tasks.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli flow-memory-rating --max-level hard
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level hard
```

After gate summary:

Semantic candidates now carry an explicit bounded score, merge with symbol and
FTS candidates at the persisted index boundary, and continue through the same
context package. Vector-only hits can participate when supplied by an available
backend, while lexical evidence keeps ranking precedence.

## Phase 2 Near Exit

Implemented retrieval/indexer coverage:

- Context package, evidence refs, safety decisions, and bilingual query aliases.
- Structured index files, chunks, line ranges, hashes, and Python symbols.
- Incremental scan manifests and safe changed-file re-indexing.
- SQLite `knowledge.db` FTS persistence plus persisted symbol candidates.
- Local `ripgrep` exact retrieval with line provenance.
- Optional vector candidate merge path with lexical precedence.

Remaining Phase 2 hardening before closure:

- Bind a real optional `sqlite-vec` adapter or document the fallback strategy
  for environments without the extension.
- Add a single orchestration command that scans a project, updates
  `knowledge.db`, and retrieves from the refreshed index.
- Re-run the Phase 1 plus completed Phase 2 full gate sweep for exit evidence.
