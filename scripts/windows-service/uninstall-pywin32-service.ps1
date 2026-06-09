<#
.SYNOPSIS
    Uninstall AI Local Agent Runtime pywin32 Windows Service.
.DESCRIPTION
    Removes the pywin32-based Windows Service without deleting workspace data.
    Requires Administrator elevation.
.PARAMETER DryRun
    If set, simulate uninstallation without modifying the system.
.EXAMPLE
    .\uninstall-pywin32-service.ps1 -DryRun
    .\uninstall-pywin32-service.ps1
#>
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if ($DryRun) {
    python -m ai_local.cli service uninstall --dry-run --strategy pywin32
    exit $LASTEXITCODE
}

Write-Host "Removing AI Local Agent Runtime (pywin32) service..."
python -m ai_local.cli service uninstall --strategy pywin32
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Uninstall failed. See output above."
    exit $LASTEXITCODE
}
Write-Host "Service removed. Workspace data preserved."
