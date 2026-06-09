<#
.SYNOPSIS
    Install AI Local Agent Runtime as a Windows Service via pywin32.
.DESCRIPTION
    Installs the daemon as a Windows Service using pywin32 (not NSSM).
    Requires Administrator elevation and pywin32 installed.
.PARAMETER Workspace
    Path to the initialised workspace directory.
.PARAMETER Startup
    Startup type: "auto" (automatic) or "manual" (manual, default).
.PARAMETER DryRun
    If set, simulate the installation without modifying the system.
.EXAMPLE
    .\install-pywin32-service.ps1 -Workspace C:\temp\ai-local-smoke -DryRun
    .\install-pywin32-service.ps1 -Workspace C:\temp\ai-local-smoke -Startup auto
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [ValidateSet("auto", "manual")]
    [string]$Startup = "manual",

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if ($DryRun) {
    python -m ai_local.cli service install --dry-run --strategy pywin32 --workspace $Workspace
    exit $LASTEXITCODE
}

Write-Host "Installing AI Local Agent Runtime (pywin32) service..."
python -m ai_local.cli service install --strategy pywin32 --workspace $Workspace
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Installation failed. See output above."
    exit $LASTEXITCODE
}
Write-Host "Installation complete."
