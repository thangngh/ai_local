# Prompt Injection Refusal Gate

This harness validates prompt-injection recognition and graceful refusal behavior.

Covered decisions:

- `refuse`
- `deny`
- `ask_user`
- `quarantine_injected_part`
- `stop`

The gate distinguishes between:

- pure prompt injection
- mixed legitimate requirement plus injected instruction
- fake approval
- policy shadowing
- secret exfiltration
- destructive tool override

Deep max hop:

- 50

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli prompt-injection
```

