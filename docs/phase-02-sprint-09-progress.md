# Phase 02 Sprint 09 Progress

Sprint focus:

- `F-RET-009`: vector provider boundary and local fallback hardening
- `F-RET-010`: deleted-file cleanup, index maintenance, and agent-loop handoff

## Functional `F-RET-009`

Before gate summary:

Sprint 07 allowed optional semantic chunks into persisted retrieval, and Sprint
08 completed project refresh orchestration. The integration point still required
callers to prepare raw vector chunks before retrieval, which would couple future
`sqlite-vec` work to every caller.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level hard
.\.venv\Scripts\python -m ai_local.cli flow-memory-rating --max-level hard
```

After gate summary:

Persisted retrieval and project refresh now accept a vector candidate provider
protocol. `NullVectorProvider` keeps the local-first fallback explicit when no
vector backend is configured, while future SQLite-vector adapters can return
semantic chunks through one bounded search method.

## Sprint Exit

- Retrieval callers can use provider-based semantic candidates or the prior
  raw chunk path.
- Project refresh orchestration passes vector providers to persisted retrieval.
- The no-vector path is explicit and deterministic.
- Lexical and symbol candidates still rank through the same context package.

## Functional `F-RET-010`

Before gate summary:

Phase 2 exit review found three operational gaps after the provider boundary:
files removed from a project still needed stale row reconciliation,
maintenance commands needed a stable CLI surface, and the agent loop needed a
runtime handoff into retrieval without owning index scan logic.

Patch gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli agent-loop
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level hard
.\.venv\Scripts\python -m ai_local.cli promote
```

After gate summary:

Project refresh now removes indexed file, chunk, symbol, and FTS rows for files
that disappear from the scan set. `project-index` and `project-index-stats`
provide local maintenance output. The agent loop accepts a configured context
retriever and calls it only when the plan gate enters `RETRIEVE`.

## sqlite-vec Decision

Phase 2 now includes the optional `SqliteVecProvider` implementation and the
deterministic `HashingTextEmbedder` baseline. The provider creates vector
schema only when the `sqlite-vec` extra is available, syncs embeddings by chunk
hash and embedder name, prunes stale vector rows, and keeps
`NullVectorProvider` as the no-extension path.

## Functional `F-RET-011`

Before gate summary:

The remaining Phase 2 checklist still needed a rebuild path, an agent-loop
integration test using the real project retriever, a parser expansion boundary,
and one concrete optional vector adapter rather than only a provider protocol.

Patch gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli agent-loop
.\.venv\Scripts\python -m ai_local.cli memory-sql
.\.venv\Scripts\python -m ai_local.cli promote
```

After gate summary:

`project-index-rebuild` clears persisted retrieval rows and refreshes them from
the current project. `ProjectRetriever` is exercised through the agent loop.
Symbol indexing now uses a registry and has a Tree-sitter adapter surface for
JS/TS grammar packages when installed. The optional SQLite vector provider owns
extension loading, `vec0` schema, embedding sync, stale-vector pruning, and KNN
candidate search.

## Remaining Optional Depth

- Install grammar packages and wire language-specific Tree-sitter declaration
  maps for JavaScript/TypeScript in the default extractor registry.
- Replace the deterministic hashing embedder with a selected local embedding
  model when semantic quality becomes a product requirement.
