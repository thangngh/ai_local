# Phase 02 Sprint 02 Progress

Sprint focus:

- `F-RET-002`: indexer MVP inputs and retrieval bridge

## Functional `F-RET-002`

Before gate summary:

The second Phase 2 sprint tightens structured retrieval inputs. File metadata,
chunk hashes, line ranges, and Python symbols already exist; this patch makes
source refs and symbol anchors explicit, supports deterministic batch indexing,
and lets retrieval consume indexed documents rather than requiring callers to
flatten chunks by hand.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval --max-level medium
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level medium
```

After gate summary:

Retrieval and memory SQL focused gates passed. Indexed files now expose file
source refs, chunks carry line source refs and overlapping symbol anchors, batch
indexing preserves stable document order, and the retrieval bridge consumes
indexed documents while keeping the Sprint 01 context package contract intact.

## Sprint Exit

Phase 2 Sprint 02 indexer baseline is present:

- Indexed files carry path, language, hash, size, and file source refs.
- Indexed chunks carry content hash, source refs, line ranges, and symbol refs.
- Batch indexing turns deterministic scanned paths into indexed documents.
- Retrieval can package evidence directly from indexed documents.

The Phase 2 MVP retrieval/indexer boundary is now explicit enough for later FTS,
vector, and durable update work behind the same contracts.
