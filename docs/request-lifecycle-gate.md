# Request Lifecycle Gate

This harness validates the full request lifecycle and bridges it with conflict harnesses.

Core lifecycle:

```text
USER -> GATEWAY -> AGENT_LOOP -> KNOWLEDGE -> RETRIEVER
-> MODEL -> TOOLS -> EVALUATOR -> DECISION_GATE
```

Covered conflict outcomes:

- final answer
- ask user
- retry
- quarantine
- rollback
- dispatch once
- stop

Deep max hop:

- 50

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
```

