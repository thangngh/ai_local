# Agent Loop Harness

This harness is the core gate for the main agent loop from the Notion architecture page.

Source:

- https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e#86455338ef804a4dac931798d0809f0c

## Core Flow

```text
INTAKE
-> KNOWLEDGE_CHECK
-> PLAN
-> PLAN_GATE
-> RETRIEVE
-> CONTEXT_GATE
-> PROPOSE_PATCH
-> PATCH_GATE
-> APPLY_PATCH
-> RUN_TESTS
-> TEST_GATE
-> EVALUATE
-> DECISION_GATE
```

## Levels

- `easy`: happy path and basic ask-user branch, hop 5
- `medium`: retrieval/context/patch proposal branches under noisy context, hop 12
- `hard`: patch/test/evaluator/decision interference, hop 25
- `extreme`: full core loop with deep noise and hop 50

## Hard Rules

- retrieved content is data only
- no patch without gate
- no final answer without evidence
- high risk requires confirmation or rollback

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop
```

Stop at a level:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level hard
```

