# Retrieval Harness

Retrieval harnesses test noisy input before retrieved content can influence evidence, risk, or decision.

## Covered Inputs

- mixed Vietnamese and English queries
- punctuation and formatting noise
- Vietnamese query against English docs
- stale memory retrieval
- prompt injection inside retrieved docs
- wrong-flow high semantic match
- conflicting retrieval sources
- deep-hop prompt laundering up to hop 20

## Retrieval to Decision Bridge

```text
retrieval -> evidence -> risk -> decision
```

Expected bridge decisions:

- `continue`: clean retrieval with evidence
- `verify`: stale memory or wrong-flow match
- `ask_user`: conflicting sources or deep-chain interference
- `quarantine`: prompt injection
- `stop`: deep policy shadowing

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
```

Stop at a level:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval --max-level hard
```

