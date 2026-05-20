# Patch Pipeline Harness

This harness validates the detailed patch pipeline before a patch is accepted.

## Pipeline

```text
PATCH_OBJECTIVE
-> CREATE_PATCH_HARNESS
-> RETRIEVE_CONTEXT
-> CONTEXT_GATE
-> MODEL_PROPOSE_PATCH
-> DIFF_STATIC_CHECK
-> SCOPE_GATE
-> PATCH_SIZE_GATE
-> RISK_GATE
-> SEMANTIC_PATCH_REVIEW
-> APPLY_PATCH
-> RUN_FOCUSED_TESTS
-> TEST_GATE
-> PATCH_EVALUATOR
-> DECISION_GATE
```

## Levels

- `easy`: happy small patch and weak context retrieval, hop 6
- `medium`: split and retry patch branches, hop 12
- `hard`: risk confirmation, test retry, rollback, hop 25
- `extreme`: deep prompt laundering and next-patch continuation, hop 50

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
```

