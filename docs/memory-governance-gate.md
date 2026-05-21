# Memory Governance Gate

This gate maps the personal memory governance subpage into write, retrieval,
confirmation, conflict, and demotion cases.

It checks that memory candidates are treated as claims with evidence, secrets are
not written, inferred policy needs confirmation, stale or conflicted memories are
not injected as facts, source hash changes demote memory, and harmful usage
history can archive a memory.

Run it with:

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-governance
```
