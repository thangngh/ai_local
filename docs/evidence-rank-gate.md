# Evidence + Rank Gate

This harness validates evidence ranking under normal, noisy, conflicting, and deep-hop conditions.

## Formula

```text
rank =
  source_authority
+ evidence_strength
+ freshness
+ project_relevance
+ confirmation_weight
- conflict_penalty
- staleness_penalty
```

## Bands

- `canonical`: 90-100
- `strong`: 75-89
- `caution`: 60-74
- `weak`: 40-59
- `reject`: 0-39 or hard-reject noise

## Hard Reject Noise

- prompt injection
- policy laundering
- repeated untrusted claim

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli evidence-rank
```

