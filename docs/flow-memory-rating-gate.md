# Flow Memory Rating Gate

This gate maps the flow-aware memory subpage into cases for regression, role
binding, negative constraints, bilingual evidence retention, interference-aware
reranking, memory score selection, and token-cost pruning.

The cases keep semantic similarity from overriding active flow, evidence, scope,
utility, and explicit negative constraints.

Run it with:

```powershell
.\.venv\Scripts\python -m ai_local.cli flow-memory-rating
```
