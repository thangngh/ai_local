# Phase 5C — Windows Service Smoke Test

## Purpose

Manually validate the NSSM-based Windows Service MVP on a real Windows machine.
This document describes a step-by-step smoke test sequence that an operator
can run to confirm the service is installed, started, stopped, and removed
correctly without data loss.

## Prerequisites

| Requirement | Detail |
|---|---|
| Windows 10+ or Windows Server 2019+ | Real service actions require Windows |
| Python 3.10+ | On `PATH` or specified via `-PythonExe` |
| NSSM installed | See [NSSM download](https://nssm.cc/download) |
| Admin PowerShell | Required for real install / start / stop / uninstall |
| Workspace initialised | `python -m ai_local.cli init --workspace <path>` |
| Project wheel installed | `pip install -e .` or equivalent |

### NSSM requirement

NSSM is **not** bundled with AI Local.  Install it manually:

1. Download from https://nssm.cc/download (latest `nssm-2.24.zip`).
2. Extract `win64/nssm.exe` (or `win32/nssm.exe`) to a directory on `PATH`,
   or set `$env:NSSM_EXE` to the full path of `nssm.exe`.

Verify with:

```powershell
.\scripts\windows-service\check-nssm.ps1
```

Expected output:

```
NSSM found
PATH C:\path\to\nssm.exe
```

### Admin shell requirement

Real install, start, stop, and uninstall commands must be run from a
PowerShell session **elevated as Administrator**.  Non-admin shells will
fail with an access denied error from NSSM.

Dry-run and log-reading commands do not require admin privileges.

## Workspace initialisation

Before installing the service, initialise the workspace:

```powershell
python -m ai_local.cli init --workspace .tmp-demo
```

Verify the `.ai-local` directory was created:

```powershell
ls .tmp-demo/.ai-local/
```

Expected output — directories: `backups`, `logs`, `reports` and files:
`config.yaml`, `knowledge.db`, `runtime.db`, `tasks.db`, `audit.db`.

## Validation sequence

### 1. Dry-run validation

Run the dry‑run commands to confirm the CLI contract works without side
effects:

```powershell
python -m ai_local.cli service install --dry-run --workspace .tmp-demo
python -m ai_local.cli service uninstall --dry-run --workspace .tmp-demo
python -m ai_local.cli service start --dry-run --workspace .tmp-demo
python -m ai_local.cli service stop --dry-run --workspace .tmp-demo
python -m ai_local.cli service status --dry-run --workspace .tmp-demo
```

Each must print a `SERVICE ... dry-run` message and exit code 0.

Also run the PowerShell script wrappers in dry‑run mode:

```powershell
.\scripts\windows-service\install-backend-service.ps1 -Workspace .tmp-demo -DryRun
.\scripts\windows-service\restart-backend-service.ps1 -Workspace .tmp-demo -DryRun
.\scripts\windows-service\show-backend-service-status.ps1 -Workspace .tmp-demo -Tail 30
```

### 2. Real install

Only on Windows, in an **elevated** PowerShell:

```powershell
.\scripts\windows-service\install-backend-service.ps1 -Workspace .tmp-demo
```

Expected output:

```
Running: python -m ai_local.cli service install --workspace <absolute>...
SERVICE install PASS
NAME AI Local Agent Runtime
ID ai-local-agent-runtime
COMMAND python -m ai_local.cli daemon run --workspace <absolute> --loop --poll-interval 1.0
```

### 3. Check NSSM registered the service

```powershell
nssm status ai-local-agent-runtime
```

Or via the CLI:

```powershell
python -m ai_local.cli service status --workspace .tmp-demo
```

Expected output:

```
SERVICE status
NAME AI Local Agent Runtime
ID ai-local-agent-runtime
STATE <state>
```

The state will typically be `SERVICE_STOPPED` after install (not started).

### 4. Start the service

```powershell
.\scripts\windows-service\restart-backend-service.ps1 -Workspace .tmp-demo
```

Or directly:

```powershell
python -m ai_local.cli service start --workspace .tmp-demo
```

### 5. Check status and logs

```powershell
.\scripts\windows-service\show-backend-service-status.ps1 -Workspace .tmp-demo -Tail 30
```

This shows:

- Service status (should be `SERVICE_RUNNING`)
- Recent log lines from `.ai-local/logs/`
- Runtime control plane overview

### 6. Submit a task and confirm it's processed

```powershell
python -m ai_local.cli task submit "Smoke test task" --workspace .tmp-demo
python -m ai_local.cli runtime status --workspace .tmp-demo
```

The runtime status should show the task was processed:

```
TASKS total=1 pending=0 done=1 cancelled=0
```

### 7. Stop the service

```powershell
python -m ai_local.cli service stop --workspace .tmp-demo
```

### 8. Uninstall the service

```powershell
.\scripts\windows-service\uninstall-backend-service.ps1 -Workspace .tmp-demo
```

Expected output:

```
SERVICE uninstall PASS
NAME AI Local Agent Runtime
ID ai-local-agent-runtime
NOTE workspace data was not removed
```

### 9. Verify workspace data preserved

```powershell
ls .tmp-demo/.ai-local/reports/
ls .tmp-demo/.ai-local/logs/
ls .tmp-demo/.ai-local/backups/
```

All directories and their contents must still exist.

## Rollback

| Scenario | Steps |
|---|---|
| Service installed but not running | Run `uninstall-backend-service.ps1` |
| Service is running | Run `stop` then `uninstall` |
| Uninstall accidentally removes data | Restore from `.ai-local/backups/` if backup was taken |
| NSSM missing | Install NSSM (see prerequisites), re-run install |
| Wrong Python path | Uninstall, re-run install with `-PythonExe` |
| Workspace path changed | Uninstall, re-run install with new `--workspace` |

## Troubleshooting

| Symptom | Likely cause | Remedy |
|---|---|---|
| "NSSM not found" | NSSM not installed or not on PATH | Run `check-nssm.ps1`, install NSSM |
| "Windows only" | Running on non-Windows | Dry‑run / logs only work, real actions require Windows |
| "has not been initialised" | `init` not run | `python -m ai_local.cli init --workspace <path>` |
| Install succeeds but start fails | Workspace path not absolute, or Python not on SYSTEM PATH | Verify workspace with `nssm get ai-local-agent-runtime AppParameters` |
| Python errors in service log | Python environment mismatch | Uninstall, re-install using `-PythonExe` pointing to the correct interpreter |
| Service is running but not processing tasks | Queue empty, or daemon lock stale | Check runtime status, submit a task, check logs |
| "Access denied" with NSSM | Not running as Administrator | Re-run PowerShell as Administrator |

## Known limitations

- **Single workspace** — Only one workspace per service instance.
- **No crash recovery** — If the daemon process exits unexpectedly, the
  service stays stopped (recovery not configured in MVP).
- **No log rotation** — `daemon.log`, `service.stdout.log`, and
  `service.stderr.log` grow unboundedly.
- **NSSM external dependency** — Users must install NSSM manually.
- **Development/demo grade** — Not intended for production deployments.

## Explicit non-goals

- ❌ No service recovery policies configured.
- ❌ No automatic crash restart.
- ❌ No auto-download of NSSM.
- ❌ No bundled NSSM binary in the repository.
- ❌ No production hardening (ACLs, perf counters, event log integration).
- ❌ No multi-workspace management.
- ❌ No remote monitoring or alerting.
