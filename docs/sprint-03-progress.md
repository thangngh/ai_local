# Sprint 03 Progress

Sprint focus:

- `F-RET-001`: Hybrid retrieval and context packaging
- `F-RET-002`: Indexer MVP inputs for FTS, vectors, and symbols

## Functional `F-RET-001`

Before gate summary:

Sprint 03 adds retrieval packaging before storage engines become complex. Query
normalization keeps bilingual aliases, indexed chunks become ranked hits with
flow/evidence/interference features, and context decisions distinguish usable,
verification, quarantine, and source-conflict paths.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli flow-memory-rating --max-level hard
```

After gate summary:

Retrieval and flow-memory focused gates validate noisy and flow-sensitive
retrieval behavior. Context packages rank active-flow hits over interfering
matches, preserve conflict decisions, and quarantine chunks already marked with
prompt-injection flags.

## Functional `F-RET-002`

Before gate summary:

Indexer MVP work creates retrieval inputs with explicit metadata instead of
embedding raw strings blindly. File metadata includes path, language, size, and
content hash; text chunks keep line ranges and hashes; Python symbol extraction
provides function/class anchors for later symbol graph work.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval --max-level medium
.\.venv\Scripts\python -m ai_local.cli memory-sql --max-level medium
```

After gate summary:

Retrieval and memory SQL focused gates preserve the current indexer boundary.
Indexed documents now provide structured file/chunk/symbol inputs needed by FTS,
vector, and symbol layers without widening Sprint 03 into memory governance or a
durable index store.

## Sprint 03 Exit

Sprint 03 MVP retrieval baseline is present:

- Queries normalize punctuation and expose bilingual aliases.
- Indexed chunks become ranked retrieval hits with context decisions.
- Context packages preserve verify, quarantine, and ask-user paths.
- Indexer creates file metadata, chunk hashes, line ranges, and Python symbols.

Sprint 04 can tighten harness and patch pipeline work while later retrieval
patches swap in durable FTS/vector stores behind the structured index inputs.
