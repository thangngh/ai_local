# Phase 04 Sprint 05 Progress

Sprint focus:

- `F-EVAL-005`: observation evaluation retry, re-plan, and finish routing

## Functional `F-EVAL-005`

Before gate summary:

Phase 4 already routes score, evidence, verification, and confirmation paths.
The remaining evaluator requirement is runtime observation handling: a tool can
fail, return empty output, repeat the same action, expose an unsafe request, or
produce completion evidence that should finish the run.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level hard
.\.venv\Scripts\python -m ai_local.cli evaluation
.\.venv\Scripts\python -m ai_local.cli decision --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
```

After gate summary:

`ObservationEvaluationInput` gives the evaluator a bounded tool observation
contract. Failed observations retry before budget exhaustion and re-plan after
it; empty output verifies; repeated actions re-plan; unsafe observations stop;
and completion reaches `DONE` only when context and test evidence are present.
`AgentLoop.evaluate_observation` persists the routed run state and marks an
evidenced finish as succeeded.

## Sprint Exit

- Observation failures do not become false success paths.
- Empty output, repeated work, and unsafe observation branches are explicit.
- Finish routing requires evaluator evidence and reaches agent run completion.
- Evaluation gate config covers observation noise and hop-depth closure cases.
