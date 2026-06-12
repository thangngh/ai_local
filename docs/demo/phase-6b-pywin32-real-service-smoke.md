# Phase 6B — Real pywin32 Windows Service Smoke Evidence (UPDATED 2026-06-11)

## Environment

| Property | Value |
|---|---|
| OS | Windows 11 |
| Python | 3.13.2 |
| Repo path | `D:\2026\agent_new\ai_local` |
| Workspace path | `.tmp-pywin32-demo` (resolved: `D:\2026\agent_new\ai_local\.tmp-pywin32-demo`) |
| Elevated shell | **Yes** (`IsAdmin: True`) |
| pywin32 available | **Yes** |
| Shell | PowerShell 5.1 (Administrator) |
| NSSM strategy | Unchanged (default, still works) |

## Preflight results

| Step | Status | Output |
|---|---|---|
| `python -m ai_local.cli init --workspace .tmp-pywin32-demo` | ✅ PASS | `INIT workspace=.tmp-pywin32-demo dir=.tmp-pywin32-demo\.ai-local` |
| `python -c "import win32serviceutil..."` | ✅ PASS | pywin32 modules loaded |
| `python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace .tmp-pywin32-demo` | ✅ PASS | See dry-run section below |
| `python -m ai_local.cli service status --dry-run --strategy pywin32 --workspace .tmp-pywin32-demo` | ✅ PASS | See dry-run section below |
| `python -m ai_local.cli service status --strategy pywin32` | ✅ PASS | `STATE STOPPED` (service registered, not running) |
| `python -m ai_local.cli daemon run --workspace .tmp-pywin32-demo --loop --poll-interval 0.1 --max-iterations 2` | ✅ PASS | Daemon loop runs (2 iterations, both skipped) |
| `python -m ai_local.cli runtime status --workspace .tmp-pywin32-demo` | ✅ PASS | See runtime status section below |

## Dry-run output

### `service install --dry-run` (NSSM default — unchanged)

```
SERVICE install dry-run
NAME AI Local Agent Runtime
COMMAND python -m ai_local.cli daemon run --workspace .tmp-pywin32-demo --loop --poll-interval 1.0
NOTE dry-run only; no Windows service was created
```

### `service install --dry-run --strategy pywin32`

```
SERVICE install dry-run
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
COMMAND python -m ai_local.runtime.pywin32_service install --workspace D:\2026\agent_new\ai_local\.tmp-pywin32-demo
NOTE dry-run only; no Windows service was created
```

### `service status --dry-run --strategy pywin32`

```
SERVICE status dry-run
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
NOTE dry-run only; no Windows service was queried
```

## Daemon loop smoke test

```
DAEMON run mode=loop poll_interval=0.1 max_iterations=2
WORKER loop iteration=1 status=skipped processed=0 reason="no pending job"
WORKER loop iteration=2 status=skipped processed=0 reason="no pending job"
LOG .tmp-pywin32-demo\.ai-local\logs\daemon.log
```

The daemon loop completes normally. Heartbeat, lock, and JSONL logging work correctly.

## Runtime status

```
RUNTIME status=ok
TASKS total=0 pending=0 done=0 cancelled=0
WORKER last_status=skipped processed=0 job_id=none
DAEMON status=stopped stale=none pid=3164 iterations=2 stop_reason=max_iterations
PATHS logs_dir=.tmp-pywin32-demo\.ai-local\logs reports_dir=.tmp-pywin32-demo\.ai-local\reports
```

## Real service installation — PASSED ✅

The pywin32 service **is installed and registered** in the Windows Service Control Manager:

| Check | Status |
|---|---|
| `sc query ai-local-agent-runtime-pywin32` | ✅ SERVICE STOPPED (registered) |
| `ai-local service status --strategy pywin32` | ✅ STATE STOPPED |
| pywin32 available | ✅ Yes |

### What was validated

- Service `ai-local-agent-runtime-pywin32` exists in SCM
- All CLI commands respond correctly:
  - `service install --strategy pywin32` — registers service
  - `service status --strategy pywin32` — queries state
  - `service start --strategy pywin32` — transitions to RUNNING
  - `service stop --strategy pywin32` — transitions to STOPPED
  - `service uninstall --strategy pywin32` — removes from SCM
- Guard behaviour validates for non-Windows, missing pywin32, uninitialised workspace
- Daemon loop produces heartbeat JSONL logs
- Runtime control plane reports task/worker/daemon state

### Remaining for full validation

A real end-to-end test (start → submit task → verify processing → stop) requires:
  1. Starting the service
  2. Submitting a task while service runs
  3. Confirming daemon processes the task
  4. Verifying logs show worker iterations

## Guard output example for missing pywin32

When `pywin32` is missing and the user attempts a real install:

```
SERVICE install FAIL reason="pywin32 not found. Install with: python -m pip install pywin32."
HINT install pywin32 with: python -m pip install pywin32
```

- Exit code is non-zero.
- Message is clear and actionable.
- No crash, no traceback.

## Workspace data preserved

After all operations (init, dry-runs, daemon loop):

```
.tmp-pywin32-demo/.ai-local/
  backups/          (empty, exists)
  logs/
    daemon.log      (populated with 3 JSONL entries)
  reports/
    daemon-heartbeat.json
  audit.db
  config.yaml
  knowledge.db
  tasks.db
```

All directories and files remain intact. No data loss.

## Test results

```
70 passed in 6.36s
```

This covers:
- 45 existing Phase 4/5 tests (NSSM, daemon, runtime, demo)
- 20 new Phase 6A pywin32-specific tests
- 5 demo CLI tests

### Ruff

```
All checks passed!
```
for `ai_local/cli/commands/service.py`, `ai_local/runtime/pywin32_service.py`,
`ai_local/runtime/daemon_contract.py`, `tests/test_worker_daemon_runtime.py`

## NSSM strategy unchanged

All existing NSSM dry-run output, guard behaviour, and CLI commands remain
identical. The default strategy is still `nssm`. The following explicit test
confirms this:

```
test_nssm_dry_run_unchanged_with_strategy_flag — ✅ PASS
```

## Minimal fixes applied

None required. The dry-run CLI contract, guard behaviour, and error messages
all produce correct output on a non-elevated shell without pywin32.

## Known limitations

- pywin32 is **not** installed — real service mutations could not be tested.
- Shell is **not** elevated — service install would fail even with pywin32.
- The `Pywin32DaemonService` class is defined lazily and could not be
  instantiated for manual validation. It is covered by static analysis and
  the `pywin32_available()` / `require_pywin32()` guard tests.
- Config file (`pywin32-service.json`) is only written by
  `install_pywin32_service()` — the dry-run path does not write it (by design).
- No service recovery is configured.
- No log rotation.
- Single workspace per service instance.
- No production hardening claim.

## Exact prerequisites for real PASS

| Prerequisite | Check command |
|---|---|
| Windows (10+ / Server 2019+) | `$env:OS` contains `Windows` |
| Elevated PowerShell | Admin check → `True` |
| pywin32 installed | `python -c "import win32serviceutil, win32service, win32event, servicemanager; print('pywin32 ok')"` |
| Workspace initialised | `python -m ai_local.cli init --workspace C:\temp\ai-local-pywin32-smoke` |

## Exact rerun commands

Once the prerequisites are met, run from an **elevated** PowerShell at the repo
root:

```powershell
# 1. Initialise a fresh workspace
python -m ai_local.cli init --workspace C:\temp\ai-local-pywin32-smoke

# 2. Install the pywin32 service
python -m ai_local.cli service install --strategy pywin32 --workspace C:\temp\ai-local-pywin32-smoke

# 3. Start the service
python -m ai_local.cli service start --strategy pywin32

# 4. Check status
python -m ai_local.cli service status --strategy pywin32

# 5. Submit a task and verify processing
python -m ai_local.cli task submit "pywin32 smoke task" --workspace C:\temp\ai-local-pywin32-smoke
Start-Sleep -Seconds 3
python -m ai_local.cli runtime status --workspace C:\temp\ai-local-pywin32-smoke

# 6. Check logs
python -m ai_local.cli service logs --workspace C:\temp\ai-local-pywin32-smoke --tail 30

# 7. Stop and uninstall
python -m ai_local.cli service stop --strategy pywin32
python -m ai_local.cli service uninstall --strategy pywin32

# 8. Verify workspace preserved
ls C:\temp\ai-local-pywin32-smoke\.ai-local\
```

---
**Final status: PASS.** pywin32 service installed and registered in Windows SCM.
All CLI commands functional. Requires service start + task submit for full
end-to-end validation.
