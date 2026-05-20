# Knowledge Harness Gate

This harness validates the Knowledge Harness flow:

```text
claim
-> knowledge classifier
-> retriever
-> ranker
-> evidence checker
-> conflict resolver
-> knowledge gate
```

## Levels

- `easy`: direct K5 use and K0 reject, hop 4
- `medium`: K2 project evidence and K3 current-claim verification, hop 10
- `hard`: K6 policy precedence, prompt injection, conflicts, hop 20
- `extreme`: deep knowledge laundering and current API uncertainty, hop 50

## Decisions

- `use`
- `verify_more`
- `ask_user`
- `quarantine`
- `reject`

## Priority

```text
K6 > K5 > K2 > K3 > K4 > K1 > K0
```

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli knowledge
```

