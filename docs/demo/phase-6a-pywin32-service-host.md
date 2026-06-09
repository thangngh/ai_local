# Phase 6A — Optional pywin32 Windows Service Host Strategy

## Why pywin32

NSSM is a solid external service wrapper, but it requires a separate binary
that must be downloaded and installed.  pywin32 provides a pure-Python path
to Windows Service integration, removing the NSSM dependency for users who
prefer a self-contained Python solution.

## How it differs from NSSM

| Aspect | NSSM strategy | pywin32 strategy |
|---|---|---|
| External binary | Requires `nssm.exe` | No external binary |
| Python dependency | None (beyond stdlib) | Requires `pywin32` |
| Service identity | `ai-local-agent-runtime` | `ai-local-agent-runtime-pywin32` |
| Display name | AI Local Agent Runtime | AI Local Agent Runtime (pywin32) |
| Config mechanism | NSSM registry-based | JSON config file in workspace |
| Daemon integration | Shells out to CLI | Calls `run_daemon_loop()` directly |
| Stop mechanism | NSSM signal → `SIGTERM` | pywin32 event → `should_stop()` callback |
| Logging | NSSM stdout/stderr files | Windows EventLog |

## Required dependency

pywin32 must be installed in a Python environment accessible to the service
account:

```powershell
python -m pip install pywin32
```

**Important:** User-local Python installs may not work for `LocalSystem`
services.  Install Python system-wide or use a virtual environment accessible
to the service account.

## Global/elevated install warning

Service installation modifies the Windows Service Control Manager database.
This requires **Administrator** elevation, regardless of strategy:

```powershell
# Verify elevation
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
```

If the shell is not elevated, all real service operations fail with clear
messages.

## Commands

All commands follow the same CLI pattern as NSSM, using the `--strategy pywin32`
flag:

```powershell
# Install
python -m ai_local.cli service install --workspace .tmp-demo --strategy pywin32

# Start
python -m ai_local.cli service start --strategy pywin32

# Stop
python -m ai_local.cli service stop --strategy pywin32

# Status
python -m ai_local.cli service status --strategy pywin32

# Uninstall
python -m ai_local.cli service uninstall --strategy pywin32
```

The default strategy (`--strategy nssm`) is unchanged.

Direct module invocation is also supported:

```powershell
python -m ai_local.runtime.pywin32_service install --workspace C:\temp\ai-local-smoke
python -m ai_local.runtime.pywin32_service start
python -m ai_local.runtime.pywin32_service stop
python -m ai_local.runtime.pywin32_service status
python -m ai_local.runtime.pywin32_service remove
```

## Dry-run examples

```powershell
# pywin32 install dry-run
python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace .tmp-demo
```

Expected output:

```
SERVICE install dry-run
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
COMMAND python -m ai_local.runtime.pywin32_service install --workspace <ABSOLUTE_WORKSPACE>
NOTE dry-run only; no Windows service was created
```

```powershell
# pywin32 start dry-run
python -m ai_local.cli service start --dry-run --strategy pywin32
```

Expected output:

```
SERVICE start dry-run
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
COMMAND python -m ai_local.runtime.pywin32_service start
NOTE dry-run only; no Windows service was started
```

```powershell
# pywin32 stop dry-run
python -m ai_local.cli service stop --dry-run --strategy pywin32
```

Expected output:

```
SERVICE stop dry-run
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
COMMAND python -m ai_local.runtime.pywin32_service stop
NOTE dry-run only; no Windows service was stopped
```

```powershell
# pywin32 status dry-run
python -m ai_local.cli service status --dry-run --strategy pywin32
```

Expected output:

```
SERVICE status dry-run
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
NOTE dry-run only; no Windows service was queried
```

```powershell
# pywin32 uninstall dry-run
python -m ai_local.cli service uninstall --dry-run --strategy pywin32
```

Expected output:

```
SERVICE uninstall dry-run
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
COMMAND python -m ai_local.runtime.pywin32_service remove
NOTE dry-run only; no Windows service was removed
```

## Real validation preconditions

| Prerequisite | Check command |
|---|---|
| Windows (10+ / Server 2019+) | `$env:OS` contains `Windows` |
| Elevated PowerShell | Admin check returns `True` |
| pywin32 installed | `python -c "import win32serviceutil"` ← no error |
| Workspace initialised | `python -m ai_local.cli init --workspace <path>` |

## Real command output examples

**Missing pywin32:**

```
SERVICE install FAIL reason="pywin32 not found. Install with: python -m pip install pywin32."
HINT install pywin32 with: python -m pip install pywin32
```

**Non-Windows:**

```
SERVICE install FAIL reason="Windows only"
```

**Workspace not initialised:**

```
SERVICE install FAIL reason="Workspace <path> has not been initialised. Run `python -m ai_local.cli init --workspace <path>` first."
```

**Successful install:**

```
SERVICE install PASS
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
WORKSPACE C:\temp\ai-local-smoke
```

**Successful uninstall:**

```
SERVICE uninstall PASS
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
NOTE workspace data was not removed
```

**Successful start:**

```
SERVICE start PASS
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
```

**Successful stop:**

```
SERVICE stop PASS
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
```

**Status:**

```
SERVICE status
STRATEGY pywin32
NAME AI Local Agent Runtime (pywin32)
ID ai-local-agent-runtime-pywin32
STATE RUNNING
```

## Config file

The pywin32 service writes its configuration to:

```
<workspace>/.ai-local/reports/pywin32-service.json
```

Example:

```json
{
  "workspace": "C:\\temp\\ai-local-smoke",
  "poll_interval": 1.0,
  "service_id": "ai-local-agent-runtime-pywin32"
}
```

## Test results

```
59 passed in 5.15s
```

This includes 14 new pywin32-specific tests:

- `test_pywin32_available_returns_false_without_pywin32`
- `test_require_pywin32_raises_without_pywin32`
- `test_pywin32_lazy_imports_non_windows`
- `test_pywin32_write_config`
- `test_pywin32_read_config_missing`
- `test_pywin32_install_dry_run_exact`
- `test_pywin32_uninstall_dry_run_exact`
- `test_pywin32_start_dry_run_exact`
- `test_pywin32_stop_dry_run_exact`
- `test_pywin32_status_dry_run_exact`
- `test_pywin32_real_install_non_windows_fails`
- `test_pywin32_real_install_missing_pywin32_fails`
- `test_pywin32_real_install_uninitialized_workspace_fails`
- `test_nssm_dry_run_unchanged_with_strategy_flag`

## Validation commands

Run these to verify Phase 6A:

```powershell
python -m ai_local.cli service install --dry-run --workspace .tmp-demo
python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace .tmp-demo
python -m ai_local.cli service status --dry-run --strategy pywin32 --workspace .tmp-demo
python -m pytest tests/test_worker_daemon_runtime.py -q
python -m ruff check ai_local/cli/commands/service.py ai_local/runtime/windows_service.py ai_local/runtime/pywin32_service.py tests/test_worker_daemon_runtime.py
```

## Known limitations

- pywin32 is **not a hard dependency** — the repo imports on any platform.
- pywin32 must be installed in an environment accessible to the service account
  (user-local installs may not work for `LocalSystem`).
- No service recovery policy is configured (service stays stopped if the daemon
  loop exits unexpectedly).
- No log rotation — Windows EventLog entry size is bounded by the OS.
- Single workspace per service instance.
- No production hardening claim — this is an MVP integration.
- NSSM remains the default strategy; pywin32 is opt-in via `--strategy pywin32`.

## BLOCKED-PASS semantics

This phase follows the same **BLOCKED-PASS** convention as Phase 5:

- All dry-run and guard behaviour is validated by automated tests.
- All failure paths (non-Windows, missing pywin32, uninitialised workspace)
  produce clear error messages without crashes.
- Real service operations require:
  1. An **elevated** PowerShell session (Administrator).
  2. **pywin32 installed** in a service-accessible Python environment.
- If either precondition is unmet, the output is BLOCKED-PASS — the
  implementation is correct but the environment is insufficient for full
  validation.

## Files created

| File | Purpose |
|---|---|
| `ai_local/runtime/pywin32_service.py` | Service host module with lazy pywin32 imports |
| `docs/demo/phase-6a-pywin32-service-host.md` | This document |

## Files modified

| File | Change |
|---|---|
| `ai_local/runtime/daemon_contract.py` | Added `run_daemon_loop()` helper + `Callable` import |
| `ai_local/cli/commands/daemon.py` | Refactored loop mode to use `run_daemon_loop()` |
| `ai_local/cli/commands/service.py` | Added `--strategy` flag with pywin32 dispatch |
| `tests/test_worker_daemon_runtime.py` | Added 14 pywin32 tests |
