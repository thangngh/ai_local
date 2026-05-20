# Memory + SQL Gate

This harness validates memory behavior together with the SQL schema contract.

Core tables:

- `memory_items`
- `memory_evidence`
- `memory_conflicts`
- `memory_updates`
- `memory_usage`

Covered decisions:

- `accept`
- `verify`
- `drop`
- `demote`
- `ask_user`
- `quarantine`
- `stop`

Deep-hop policy:

- max hop depth: 50
- deep memory poisoning is quarantined
- safety policy laundering stops

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-sql
```

