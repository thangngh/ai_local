# Phase 02 Sprint 04 Progress

Sprint focus:

- `F-RET-004`: SQLite `knowledge.db` chunk persistence and FTS retrieval

## Functional `F-RET-004`

Before gate summary:

Phase 2 already has context packages, structured index documents, and
incremental manifests. The next retrieval boundary stores those rows in a
local knowledge index so lexical retrieval can search persisted chunks without
requiring callers to keep every indexed document in memory.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level medium
```

After gate summary:

Retrieval and memory SQL gates passed. The SQLite knowledge index creates file,
chunk, and FTS rows, exposes persisted manifest entries, replaces changed file
chunks atomically within a transaction, and returns FTS chunk matches through
the existing context package and decision bridge.

## Sprint Exit

Phase 2 Sprint 04 SQLite retrieval baseline is present:

- `KnowledgeIndexStore` initializes persisted indexed file/chunk and FTS5 tables.
- Indexed documents upsert into `knowledge.db` with source refs, metadata,
  symbol refs, flags, and evidence features intact.
- Re-indexed documents replace old file chunks and remove old FTS matches.
- Retrieval can package persisted FTS matches using the same ranked context
  contract as in-memory document retrieval.

Later Phase 2 work can add vector candidate search and richer SQL metadata
without changing the FTS-to-context boundary.
