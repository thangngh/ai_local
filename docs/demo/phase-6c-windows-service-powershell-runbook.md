# Phase 6C: Windows Service PowerShell Runbook and Command Checklist

## 1. Purpose

This runbook provides exact copy-paste friendly PowerShell commands to manually validate:

- **NSSM service strategy** - Non-Sucking Service Manager wrapper
- **pywin32 service strategy** - Native Windows service using pywin32
- **Daemon runtime while running under service control** - Background service execution
- **CLI remains usable while service is active** - Concurrent access validation
- **Clean stop/uninstall/kill paths** - Multiple shutdown strategies

> **⚠️ WARNING**: This is a DEMO/validation runbook, not production ready. Service strategies are experimental and may require elevated privileges.

## 2. Environment Variables

### Setup for fixed repository path:

```powershell
$Repo = "D:\2026\agent_new\ai_local"
$Workspace = "C:\temp\ai-local-service-smoke"
$Python = "python"

cd $Repo
```

### Setup for current repository path (recommended for testing):

```powershell
$Repo = (Get-Location).Path
$Workspace = "$Repo\.tmp-service-smoke"
$Python = "python"
```

## 3. Preflight

Verify environment is ready:

```powershell
# Check Python
& $Python --version

# Check CLI import
& $Python -m ai_local.cli --help

# Init workspace
& $Python -m ai_local.cli init --workspace $Workspace

# Verify workspace
Test-Path "$Workspace\.ai-local"
Get-ChildItem "$Workspace\.ai-local"

# Check admin
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator
)
"IsAdmin: $IsAdmin"
```

## 4. Baseline daemon without service

Prove the app works before service wrapping:

```powershell
& $Python -m ai_local.cli task submit "baseline daemon task" --workspace $Workspace
& $Python -m ai_local.cli daemon run --workspace $Workspace --loop --poll-interval 0.1 --max-iterations 2
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli runtime logs --workspace $Workspace --tail 20
```

## 5. NSSM strategy runbook

### 5.1 Check NSSM

```powershell
.\scripts\windows-service\check-nssm.ps1
```

Optional env var for custom NSSM location:

```powershell
$env:NSSM_EXE = "C:\tools\nssm\nssm.exe"
.\scripts\windows-service\check-nssm.ps1
```

### 5.2 Dry-run

```powershell
& $Python -m ai_local.cli service install --dry-run --workspace $Workspace
& $Python -m ai_local.cli service start --dry-run --workspace $Workspace
& $Python -m ai_local.cli service status --dry-run --workspace $Workspace
& $Python -m ai_local.cli service stop --dry-run --workspace $Workspace
& $Python -m ai_local.cli service uninstall --dry-run --workspace $Workspace
```

### 5.3 Install service

```powershell
.\scripts\windows-service\install-backend-service.ps1 -Workspace $Workspace
```

Or direct CLI:

```powershell
& $Python -m ai_local.cli service install --workspace $Workspace
```

### 5.4 Start service

```powershell
& $Python -m ai_local.cli service start --workspace $Workspace
```

Also include native check:

```powershell
Get-Service -Name "ai-local-agent-runtime" -ErrorAction SilentlyContinue
```

### 5.5 Verify service is active

```powershell
& $Python -m ai_local.cli service status --workspace $Workspace
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 30
```

### 5.6 Verify CLI still works while service is running

This is critical - CLI must remain functional:

```powershell
& $Python -m ai_local.cli task submit "service active task 1" --workspace $Workspace
Start-Sleep -Seconds 3
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli runtime snapshot --workspace $Workspace
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 50
```

**Expected behavior:**
- Task moves from pending to done
- Daemon heartbeat updates in runtime status
- Logs show worker iteration processing
- CLI commands work while service process is active

### 5.7 Restart service

```powershell
.\scripts\windows-service\restart-backend-service.ps1 -Workspace $Workspace
Start-Sleep -Seconds 3
& $Python -m ai_local.cli service status --workspace $Workspace
& $Python -m ai_local.cli runtime status --workspace $Workspace
```

### 5.8 Stop service

```powershell
& $Python -m ai_local.cli service stop --workspace $Workspace
Start-Sleep -Seconds 2
& $Python -m ai_local.cli service status --workspace $Workspace
& $Python -m ai_local.cli runtime status --workspace $Workspace
```

### 5.9 Kill fallback

**LAST RESORT ONLY** - Use these only when normal stop fails:

```powershell
# Last resort only: inspect python processes
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*ai_local.cli daemon run*" } |
  Select-Object ProcessId, CommandLine

# Last resort only: kill matching daemon process
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*ai_local.cli daemon run*" } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force
  }
```

Also include service-level native force:

```powershell
# If service control is stuck
Stop-Service -Name "ai-local-agent-runtime" -Force -ErrorAction SilentlyContinue
```

### 5.10 Uninstall service

```powershell
.\scripts\windows-service\uninstall-backend-service.ps1 -Workspace $Workspace
```

Verify workspace preserved:

```powershell
Test-Path "$Workspace\.ai-local"
Get-ChildItem "$Workspace\.ai-local"
```

## 6. pywin32 strategy runbook

### 6.1 Check pywin32

```powershell
& $Python -c "import win32serviceutil, win32service, win32event, servicemanager; print('pywin32 ok')"
```

If missing:

```powershell
& $Python -m pip install pywin32
```

> **Note**: Do not auto-install inside scripts. Install manually. Service account must be able to access that Python environment.

### 6.2 Dry-run

```powershell
& $Python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace $Workspace
& $Python -m ai_local.cli service start --dry-run --strategy pywin32 --workspace $Workspace
& $Python -m ai_local.cli service status --dry-run --strategy pywin32 --workspace $Workspace
& $Python -m ai_local.cli service stop --dry-run --strategy pywin32 --workspace $Workspace
& $Python -m ai_local.cli service uninstall --dry-run --strategy pywin32 --workspace $Workspace
```

### 6.3 Install pywin32 service

```powershell
.\scripts\windows-service\install-pywin32-service.ps1 -Workspace $Workspace
```

Or direct CLI:

```powershell
& $Python -m ai_local.cli service install --strategy pywin32 --workspace $Workspace
```

### 6.4 Start pywin32 service

```powershell
& $Python -m ai_local.cli service start --strategy pywin32 --workspace $Workspace
```

Native check:

```powershell
Get-Service -Name "ai-local-agent-runtime-pywin32" -ErrorAction SilentlyContinue
```

### 6.5 Verify pywin32 active service

```powershell
& $Python -m ai_local.cli service status --strategy pywin32 --workspace $Workspace
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 30
```

### 6.6 Verify active CLI with pywin32 service running

```powershell
& $Python -m ai_local.cli task submit "pywin32 active task 1" --workspace $Workspace
Start-Sleep -Seconds 3
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli runtime snapshot --workspace $Workspace
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 50
```

### 6.7 Stop pywin32 service

```powershell
& $Python -m ai_local.cli service stop --strategy pywin32 --workspace $Workspace
Start-Sleep -Seconds 2
& $Python -m ai_local.cli service status --strategy pywin32 --workspace $Workspace
```

### 6.8 Kill fallback for pywin32

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*pywin32_service*" -or $_.CommandLine -like "*ai_local*" } |
  Select-Object ProcessId, CommandLine

Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*pywin32_service*" -or $_.CommandLine -like "*ai_local*" } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force
  }
```

Native force:

```powershell
Stop-Service -Name "ai-local-agent-runtime-pywin32" -Force -ErrorAction SilentlyContinue
```

### 6.9 Uninstall pywin32 service

```powershell
.\scripts\windows-service\uninstall-pywin32-service.ps1 -Workspace $Workspace
```

Or:

```powershell
& $Python -m ai_local.cli service uninstall --strategy pywin32 --workspace $Workspace
```

Verify workspace preserved:

```powershell
Test-Path "$Workspace\.ai-local"
Get-ChildItem "$Workspace\.ai-local"
```

## 7. One-shot full smoke script blocks

### NSSM full smoke

```powershell
$Repo = "D:\2026\agent_new\ai_local"
$Workspace = "C:\temp\ai-local-nssm-smoke"
$Python = "python"
cd $Repo

& $Python -m ai_local.cli init --workspace $Workspace
.\scripts\windows-service\check-nssm.ps1
& $Python -m ai_local.cli service install --dry-run --workspace $Workspace
.\scripts\windows-service\install-backend-service.ps1 -Workspace $Workspace
& $Python -m ai_local.cli service start --workspace $Workspace
Start-Sleep -Seconds 3
& $Python -m ai_local.cli task submit "nssm smoke task" --workspace $Workspace
Start-Sleep -Seconds 3
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 50
& $Python -m ai_local.cli service stop --workspace $Workspace
.\scripts\windows-service\uninstall-backend-service.ps1 -Workspace $Workspace
Test-Path "$Workspace\.ai-local"
```

### pywin32 full smoke

```powershell
$Repo = "D:\2026\agent_new\ai_local"
$Workspace = "C:\temp\ai-local-pywin32-smoke"
$Python = "python"
cd $Repo

& $Python -m ai_local.cli init --workspace $Workspace
& $Python -c "import win32serviceutil, win32service, win32event, servicemanager; print('pywin32 ok')"
& $Python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace $Workspace
.\scripts\windows-service\install-pywin32-service.ps1 -Workspace $Workspace
& $Python -m ai_local.cli service start --strategy pywin32 --workspace $Workspace
Start-Sleep -Seconds 3
& $Python -m ai_local.cli task submit "pywin32 smoke task" --workspace $Workspace
Start-Sleep -Seconds 3
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 50
& $Python -m ai_local.cli service stop --strategy pywin32 --workspace $Workspace
.\scripts\windows-service\uninstall-pywin32-service.ps1 -Workspace $Workspace
Test-Path "$Workspace\.ai-local"
```

## 8. Expected pass criteria

| Operation | Expected Result |
|-----------|----------------|
| service install PASS | Command succeeds with no errors |
| service start PASS | Service starts and shows 'running' status |
| service status shows running | CLI and native commands confirm service is active |
| task submitted while service active | Task moves from pending → done state |
| runtime status shows task done | Completed tasks appear in runtime snapshot |
| daemon heartbeat updates | Heartbeat file shows active iterations |
| logs contain worker iterations | JSONL logs show processing of submitted tasks |
| service stop PASS | Service stops gracefully |
| service uninstall PASS | Service removed cleanly |
| workspace still exists | `.ai-local` directory preserved |

## 9. Failure handling

| Symptom | Likely cause | Command |
|---------|-------------|---------|
| pywin32 not found | dependency missing | `python -m pip install pywin32` |
| NSSM missing | NSSM not installed | `set $env:NSSM_EXE` |
| service starts then stops | Python path/workdir issue | check `service.stderr.log` |
| task stays pending | daemon not running | `runtime status`, `service logs` |
| status says access denied | not admin | reopen PowerShell as Administrator |
| uninstall fails | service still running | `stop`/`kill` fallback |

## 10. Tests

### Document validation checklist:

- [x] Runbook document exists at `docs/demo/phase-6c-windows-service-powershell-runbook.md`
- [x] Contains NSSM full smoke block
- [x] Contains pywin32 full smoke block  
- [x] Contains task submit while service active
- [x] Contains kill fallback commands
- [x] Contains uninstall and workspace preservation check
- [x] Contains "not production ready" warning

## 11. Validation

Run these commands to verify the runbook and associated code:

```powershell
# Test the CLI and runtime functionality
python -m pytest tests/test_demo_cli.py tests/test_worker_daemon_runtime.py -q

# Check code quality
python -m ruff check ai_local/cli/commands/service.py ai_local/runtime/windows_service.py ai_local/runtime/pywin32_service.py ai_local/runtime/daemon_contract.py tests/test_worker_daemon_runtime.py
```

---

**End of Phase 6C**: Windows Service PowerShell Runbook and Command Checklist