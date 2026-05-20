# Evaluation Gate Harness

This harness validates the Evaluation Gate scoring and threshold behavior.

## Score Formula

```text
final_score =
  0.25 * correctness
+ 0.20 * completeness
+ 0.20 * evidence_quality
+ 0.15 * requirement_match
+ 0.10 * test_status
- 0.10 * ambiguity
- 0.10 * risk
```

## Bands

- `accept`: high score, low risk, enough evidence, tests present
- `retry`: medium score or requirement mismatch
- `verify`: weak evidence
- `ask_user`: high ambiguity
- `stop`: high risk

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli evaluation
```

