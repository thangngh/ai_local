# Sprint 05 Progress

Sprint focus:

- `F-EVAL-001`: evaluator output, decision policy, and confirmation manager flow

## Functional `F-EVAL-001`

Before gate summary:

Sprint 05 turns the evaluation gates into runtime decisions. Evaluation output
must preserve score fields, final score, retry budget, reasons, and protected
security branches before the decision layer asks a person or promotes a patch.
Confirmation must carry structured options, impact, recommendation, and evidence
before risky work can resume.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli evaluation
.\.venv\Scripts\python -m ai_local.cli decision
.\.venv\Scripts\python -m ai_local.cli confirmation
```

After gate summary:

Evaluation, decision, and confirmation focused gates passed. Runtime evaluation
now emits reasons for accept, retry, verify, ask-user, quarantine, and stop
paths. Confirmation routes technical risk to a tech lead, destructive actions to
current-user approval, conflicting answers back to a structured question, and
confirmed knowledge to K5 or K6 without treating safety policy as preference.

## Sprint 05 Exit

Sprint 05 decision runtime baseline is present:

- Evaluation results preserve score input, derived score, retry count, reason,
  and security signal.
- Decision policy matches gate thresholds for risk, ambiguity, evidence quality,
  requirement match, retry budget, and protected tool or memory conflicts.
- Confirmation requests require structured summaries, options, impact,
  recommendation, and evidence.
- Confirmation resolution rejects laundered approval, quarantines injected
  options, saves confirmed facts as K5, and saves confirmed policy as K6.

Sprint 06 can build knowledge claims and evidence rank on top of explicit
confirmation and decision outputs.
