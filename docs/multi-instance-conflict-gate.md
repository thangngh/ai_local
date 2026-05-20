# Multi-Instance Conflict Gate

This harness covers deep conflicts where multiple instances disagree and no instance is clearly right or wrong.

Required outcomes:

- choose a path only when one valid path exists
- ask the user when equal-authority instances conflict
- defer when evidence is missing
- stop when every route is unsafe or invalid

Deep max hop:

- 50

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli multi-conflict
```

