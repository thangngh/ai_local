# Phase 5E — Windows Service Readiness

## Current status

**BLOCKED-PASS.**  The Windows Service MVP is implemented and safely guarded.
All tests pass, all dry-run output matches the contract, and guard behaviour
(no NSSM, non-Windows, uninitialised workspace) produces clear error messages
without crashes.  Real elevated NSSM service validation is pending.

## What is implemented

| Area | Status |
|---|---|
| `ai_local/runtime/windows_service.py` — NSSM helpers | ✅ Implemented, tested with mocks |
| `ai_local/cli/commands/service.py` — CLI commands | ✅ Implemented, dry-run exact, real paths guard |
| `scripts/windows-service/check-nssm.ps1` | ✅ Written |
| `scripts/windows-service/install-backend-service.ps1` | ✅ Written |
| `scripts/windows-service/uninstall-backend-service.ps1` | ✅ Written |
| `scripts/windows-service/restart-backend-service.ps1` | ✅ Written |
| `scripts/windows-service/show-backend-service-status.ps1` | ✅ Written |
| `docs/demo/phase-5c-windows-service-smoke.md` — operator docs | ✅ Written |

## What is validated by tests

- **50 tests pass** covering:
  - Dry-run output for all 6 service commands (exact contract match).
  - Real install on non-Windows fails with "Windows only".
  - Real install with missing NSSM fails with "NSSM not found".
  - Real install with uninitialised workspace fails with clear message.
  - Mocked NSSM install calls the expected NSSM arguments.
  - Mocked NSSM uninstall does not delete workspace data.
  - Mocked NSSM start/stop/status pass through expected args.
  - `service logs` reads daemon log lines.
  - `service logs` prints `LOGS none` when no log exists.
  - PowerShell scripts exist and do not contain auto-download URLs.
  - Uninstall script does not delete reports/backups/db.
  - All scripts have `-DryRun` switches.
  - Documentation lists required validation commands.
  - Documentation does not claim production-grade service.

## What is validated by dry-run

- `service install --dry-run` — correct output, no system mutation.
- `service uninstall --dry-run` — correct output, no system mutation.
- `service start --dry-run` — correct output, no system mutation.
- `service stop --dry-run` — correct output, no system mutation.
- `service status --dry-run` — correct output, no system mutation.
- `service logs` — reads local daemon log, cross-platform.

## What is blocked

Real service installation could not be validated because:

| Blocker | Detail |
|---|---|
| Shell not elevated | `IsAdmin: False`. NSSM service mutations require Administrator. |
| NSSM not installed | `check-nssm.ps1` reports "NSSM missing". NSSM is not on `PATH` and `$env:NSSM_EXE` is not set. |

Both are environmental, not code defects.  The guard code handles them correctly
(clear error, non-zero exit, no crash).

## Exact prerequisites for real PASS

| Prerequisite | Check command |
|---|---|
| Windows (10+ / Server 2019+) | `$env:OS` contains `Windows` |
| Elevated PowerShell | `([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)` → `True` |
| NSSM installed | `.\scripts\windows-service\check-nssm.ps1` → `NSSM found` |
| Workspace initialised | `python -m ai_local.cli init --workspace <path>` |
| Python on PATH for LocalSystem | Verified via NSSM path capture at install time |

## Exact rerun commands

Once the prerequisites are met, run from an **elevated** PowerShell at the repo
root:

```powershell
# 1. Initialise a fresh workspace
python -m ai_local.cli init --workspace C:\temp\ai-local-smoke

# 2. Install the service
.\scripts\windows-service\install-backend-service.ps1 -Workspace C:\temp\ai-local-smoke

# 3. Start the service
.\scripts\windows-service\restart-backend-service.ps1 -Workspace C:\temp\ai-local-smoke

# 4. Check status and logs
.\scripts\windows-service\show-backend-service-status.ps1 -Workspace C:\temp\ai-local-smoke -Tail 30

# 5. Submit a task and verify processing
python -m ai_local.cli task submit "Smoke test" --workspace C:\temp\ai-local-smoke
python -m ai_local.cli runtime status --workspace C:\temp\ai-local-smoke

# 6. Stop and uninstall
python -m ai_local.cli service stop --workspace C:\temp\ai-local-smoke
.\scripts\windows-service\uninstall-backend-service.ps1 -Workspace C:\temp\ai-local-smoke

# 7. Verify workspace preserved
ls C:\temp\ai-local-smoke\.ai-local\
```

## What must not be claimed yet

- ❌ Not "fully validated on a real Windows service".
- ❌ Not "production ready".
- ❌ Not "NSSM-free" — NSSM is still a required external dependency.
- ❌ Not "recovery capable" — no crash restart or failure recovery configured.
- ❌ Not "multi-workspace capable".
- ❌ Not "log rotation capable".
- ❌ Not "monitored or alertable".

## Known limitations

- Single workspace per service instance.
- No crash recovery (service stays stopped if daemon exits unexpectedly).
- No log rotation (`daemon.log`, `service.stdout.log`, `service.stderr.log` grow unboundedly).
- NSSM external dependency not yet validated in CI or real manual run.
- Workspace `runtime.db` is not created by `init` — created on first use by runtime logic.  This is expected.
- Service runs as `LocalSystem`; not designed for per-user instances.

## Next manual validation path

1. Install NSSM from https://nssm.cc/download.
2. Open PowerShell **as Administrator**.
3. Navigate to the repository root.
4. Run the rerun commands listed above.
5. Confirm all steps produce expected output (or document any failures).
6. If failures are found, they are bugs in the Python CLI or NSSM configuration
   — not guard-code gaps.
7. Report results and either fix bugs (Phase 5F) or close the MVP.
