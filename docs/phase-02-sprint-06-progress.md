# Phase 02 Sprint 06 Progress

Sprint focus:

- `F-RET-006`: persisted symbol candidates for code retrieval

## Functional `F-RET-006`

Before gate summary:

Phase 2 already persists file and chunk rows in `knowledge.db` and can retrieve
local exact matches through `ripgrep`. Python symbol extraction was only carried
as chunk metadata, so durable code retrieval could not query indexed
function/class anchors directly.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level hard
```

After gate summary:

SQLite symbol rows now retain file, kind, name, range, and source refs. Symbol
lookups return the overlapping code chunk as a high-evidence candidate before
FTS candidates are packed into the existing context package and decision path.

## Sprint Exit

Phase 2 Sprint 06 symbol retrieval baseline is present:

- `KnowledgeIndexStore` persists extracted Python function/class anchors.
- Re-indexing a document removes stale symbols with stale chunks.
- Symbol query candidates retain line refs, chunk content, and symbol refs.
- Persisted symbol and FTS candidates share the same ranked retrieval package.

Later Phase 2 work can add vector candidate search behind the same candidate
merge boundary without changing context consumers.
