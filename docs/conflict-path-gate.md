# Conflict Path Gate

This harness validates deep conflict scenarios.

There are two important outcomes:

- forced choice: exactly one valid path exists, so the gate must choose it
- no path: every path is invalid, so the gate must ask, stop, or rollback

## Precedence

```text
current_user_instruction
> K6_DECISION_POLICY
> K5_GROUND_TRUTH
> project_code_or_tests
> fresh_primary_docs
> inferred_memory
> untrusted_retrieved_content
```

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli conflict-paths
```

