# Patch Levels

Patch levels provide shared limits for small patch, patch pipeline, and agent-loop harnesses.

## Levels

| Level | Files | Lines | Hop | Risk Ceiling | Confirmation |
| --- | ---: | ---: | ---: | ---: | --- |
| easy | 1 | 40 | 5 | 0.30 | no |
| medium | 2 | 100 | 12 | 0.50 | no |
| hard | 3 | 180 | 25 | 0.70 | yes |
| extreme | 3 | 240 | 50 | 0.85 | yes |

## Global Rules

- no patch without requirement ID
- no patch without harness
- no production patch before harness review
- no dependency change without confirmation
- no schema change without confirmation
- no public API change without confirmation
- rollback on failed required gate

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-levels
```

