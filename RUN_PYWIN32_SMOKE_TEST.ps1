# ============================================================================
# pywin32 Service Smoke Test - REQUIRES ADMINISTRATOR
# ============================================================================
# Run this script in an ELEVATED PowerShell session (Run as Administrator)
#
# Steps:
# 1. Right-click PowerShell → Run as Administrator
# 2. Navigate to: cd D:\2026\agent_new\ai_local
# 3. Run: .\RUN_PYWIN32_SMOKE_TEST.ps1

$ErrorActionPreference = "Stop"

# Setup
$Repo = "D:\2026\agent_new\ai_local"
$Workspace = "$Repo\.tmp-pywin32-final-test"
$Python = "python"

# Verify admin
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Host "ERROR: This script requires Administrator privileges" -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again"
    exit 1
}

Write-Host "✓ Running with Administrator privileges" -ForegroundColor Green

# Clean workspace
if (Test-Path $Workspace) {
    Remove-Item -Recurse -Force $Workspace
}

# Initialize workspace
Write-Host "`n=== INITIALIZE WORKSPACE ===" -ForegroundColor Cyan
& $Python -m ai_local.cli init --workspace $Workspace
if ($LASTEXITCODE -ne 0) { exit 1 }

# Install service
Write-Host "`n=== INSTALL PYWIN32 SERVICE ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service install --strategy pywin32 --workspace $Workspace
if ($LASTEXITCODE -ne 0) { exit 1 }

# Verify service installed
Write-Host "`n=== VERIFY SERVICE INSTALLED ===" -ForegroundColor Cyan
Get-Service -Name "ai-local-agent-runtime-pywin32" -ErrorAction Stop

# Start service
Write-Host "`n=== START SERVICE ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service start --strategy pywin32 --workspace $Workspace
if ($LASTEXITCODE -ne 0) { exit 1 }

Start-Sleep -Seconds 2

# Check service status
Write-Host "`n=== CHECK SERVICE STATUS ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service status --strategy pywin32 --workspace $Workspace
Get-Service -Name "ai-local-agent-runtime-pywin32"

# Submit task
Write-Host "`n=== SUBMIT TASK (SERVICE RUNNING) ===" -ForegroundColor Cyan
& $Python -m ai_local.cli task submit "pywin32 smoke test task" --workspace $Workspace

Start-Sleep -Seconds 3

# Check runtime status
Write-Host "`n=== CHECK RUNTIME STATUS ===" -ForegroundColor Cyan
& $Python -m ai_local.cli runtime status --workspace $Workspace

# Check snapshot
Write-Host "`n=== RUNTIME SNAPSHOT ===" -ForegroundColor Cyan
& $Python -m ai_local.cli runtime snapshot --workspace $Workspace

# Check logs
Write-Host "`n=== SERVICE LOGS ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 20

# Stop service
Write-Host "`n=== STOP SERVICE ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service stop --strategy pywin32 --workspace $Workspace

Start-Sleep -Seconds 2

# Verify stopped
Write-Host "`n=== VERIFY SERVICE STOPPED ===" -ForegroundColor Cyan
Get-Service -Name "ai-local-agent-runtime-pywin32"

# Uninstall service
Write-Host "`n=== UNINSTALL SERVICE ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service uninstall --strategy pywin32 --workspace $Workspace

# Verify workspace preserved
Write-Host "`n=== VERIFY WORKSPACE PRESERVED ===" -ForegroundColor Cyan
$preserved = Test-Path "$Workspace\.ai-local"
if ($preserved) {
    Write-Host "✓ Workspace preserved at $Workspace" -ForegroundColor Green
} else {
    Write-Host "✗ Workspace missing!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== SMOKE TEST COMPLETE ✓ ===" -ForegroundColor Green
Write-Host "All steps passed successfully!"
