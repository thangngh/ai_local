# Phase 02 Sprint 05 Progress

Sprint focus:

- `F-RET-005`: ripgrep exact local retrieval into context packages

## Functional `F-RET-005`

Before gate summary:

Requirements call for local `ripgrep` retrieval with line source references.
The project already had a subprocess wrapper, but it returned raw stdout rather
than retrieval evidence. This sprint turns `rg` line matches into indexed exact
chunks and sends them through the same context package and decision bridge as
in-memory and FTS-backed candidates.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli flow-memory-rating --max-level hard
```

After gate summary:

Retrieval and flow-memory gates passed. Ripgrep now emits line-numbered matches,
the parser preserves file and line provenance, exact matches become high-evidence
chunks, and local exact search returns selected evidence refs through the
existing retrieval package.

## Sprint Exit

Phase 2 Sprint 05 local exact retrieval baseline is present:

- `rg` subprocess output includes line numbers and no color/header noise.
- Parsed exact matches retain file path, line number, and line text.
- Exact local matches convert to retrieval chunks with line source refs.
- Ripgrep candidates enter the same rank/context packaging path as SQLite FTS
  and indexed documents.
