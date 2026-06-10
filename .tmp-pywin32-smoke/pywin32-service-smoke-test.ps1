# pywin32 Service Smoke Test
# Run this script in an ELEVATED PowerShell session (Run as Administrator)

$Repo = "D:\2026\agent_new\ai_local"
$Workspace = "$Repo\.tmp-pywin32-smoke"
$Python = "python"

Set-Location $Repo

# Verify workspace exists
if (-not (Test-Path "$Workspace\.ai-local")) {
    Write-Host "Workspace not initialized. Run: python -m ai_local.cli init --workspace $Workspace"
    exit 1
}

# 1. Install pywin32 service
Write-Host "`n=== STEP 1: Install pywin32 service ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service install --strategy pywin32 --workspace $Workspace

# 2. Check service status (native)
Write-Host "`n=== STEP 2: Check service installed (native) ===" -ForegroundColor Cyan
Get-Service -Name "ai-local-agent-runtime-pywin32" -ErrorAction SilentlyContinue

# 3. Start service
Write-Host "`n=== STEP 3: Start pywin32 service ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service start --strategy pywin32 --workspace $Workspace

Start-Sleep -Seconds 2

# 4. Check service running
Write-Host "`n=== STEP 4: Verify service is running ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service status --strategy pywin32 --workspace $Workspace
Get-Service -Name "ai-local-agent-runtime-pywin32"

# 5. Submit task while service active
Write-Host "`n=== STEP 5: Submit task while service active ===" -ForegroundColor Cyan
& $Python -m ai_local.cli task submit "pywin32 smoke test task" --workspace $Workspace

Start-Sleep -Seconds 3

# 6. Check runtime status
Write-Host "`n=== STEP 6: Check runtime status ===" -ForegroundColor Cyan
& $Python -m ai_local.cli runtime status --workspace $Workspace
& $Python -m ai_local.cli runtime snapshot --workspace $Workspace

# 7. Check logs
Write-Host "`n=== STEP 7: Check service logs ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service logs --workspace $Workspace --tail 30

# 8. Stop service
Write-Host "`n=== STEP 8: Stop pywin32 service ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service stop --strategy pywin32 --workspace $Workspace

Start-Sleep -Seconds 2

# 9. Verify service stopped
Write-Host "`n=== STEP 9: Verify service stopped ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service status --strategy pywin32 --workspace $Workspace
Get-Service -Name "ai-local-agent-runtime-pywin32"

# 10. Uninstall service
Write-Host "`n=== STEP 10: Uninstall pywin32 service ===" -ForegroundColor Cyan
& $Python -m ai_local.cli service uninstall --strategy pywin32 --workspace $Workspace

# 11. Verify workspace preserved
Write-Host "`n=== STEP 11: Verify workspace preserved ===" -ForegroundColor Cyan
Test-Path "$Workspace\.ai-local"
Get-ChildItem "$Workspace\.ai-local" | Select-Object Name

Write-Host "`n=== SMOKE TEST COMPLETE ===" -ForegroundColor Green
Write-Host "Check Windows Event Log for service messages:"
Write-Host "  Get-WinEvent -LogName Application | Where-Object {`$_.ProviderName -like '*Python*' -or `$_.Message -like '*ai-local*'} | Select-Object -First 20"
