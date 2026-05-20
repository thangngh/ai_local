# Thread Control Gate

The thread control gate validates how the runtime handles state changes for a
conversation thread before implementation work changes the thread manager.

It covers:

- user-driven pause, resume, interrupt, and archive decisions
- stale context after a newer user message arrives
- duplicate outbox dispatch on resumed threads
- retrieved-content or tool-output attempts to control the thread
- memory snapshot conflicts that require confirmation
- deep multi-module conflicts up to hop depth 50

The gate is configured in `configs/thread_control_gates.yaml` and executed with:

```powershell
.\.venv\Scripts\python -m ai_local.cli thread-control
```

The harness treats direct current-user input as the only authority that can
control a thread without another confirmation step. Retrieved content, tool
output, memory snapshots, and mixed multi-instance evidence can inform the
decision, but cannot pause, resume, interrupt, or archive a thread by themselves.
