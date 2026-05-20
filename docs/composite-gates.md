# Composite Gates

Composite gates validate the full chain across modules:

```text
task -> patch -> gate -> evidence -> score -> risk -> decision -> security
```

They are configured as 10 gates across four levels.

## Gate Set

| ID | Level | Purpose |
| --- | --- | --- |
| G01 | easy | Task intake has complete source coverage. |
| G02 | easy | Requirement scope maps to patch scope. |
| G03 | easy | Patch cannot bypass small focused harness. |
| G04 | medium | Gate results bind to audit evidence. |
| G05 | medium | Evidence is converted into score components. |
| G06 | medium | Score is checked against risk, not used alone. |
| G07 | hard | Risk must pass security/tool-policy checks. |
| G08 | hard | Approved side effects go through outbox idempotency. |
| G09 | hard | Memory/retrieval interference is verified or dropped. |
| G10 | extreme | Full deep-hop chain through all core modules up to hop 20. |

## Security Gate

The user term `secrior` is treated as an alias for the security decision layer:

- prompt firewall
- permission engine
- tool policy
- secret/sensitive-data handling
- deny/quarantine/stop decisions

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli composite
```

Stop at a level:

```powershell
.\.venv\Scripts\python -m ai_local.cli composite --max-level hard
```

