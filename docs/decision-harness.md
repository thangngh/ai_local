# Decision Harness

Decision harnesses focus on the final choice layer:

```text
score + risk + ambiguity + retries + security signal -> decision
```

They cover basic, combined, noisy, and deep-hop flows.

## Levels

- `easy`: accept and ask-user basics.
- `medium`: retry budget and evidence-to-score decisions.
- `hard`: security, tool policy, memory conflict, and quarantine/verify behavior.
- `extreme`: deep-hop noisy chains up to hop 20.

## Decisions

- `accept`
- `retry`
- `ask_user`
- `verify`
- `quarantine`
- `stop`

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli decision
```

Stop at a level:

```powershell
.\.venv\Scripts\python -m ai_local.cli decision --max-level hard
```

