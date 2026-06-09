<#
.SYNOPSIS
    Show pywin32 Windows Service status and recent log entries.
.DESCRIPTION
    Displays the current status of the AI Local Agent Runtime (pywin32)
    service and optionally tails the daemon log.
.PARAMETER Tail
    Number of recent log lines to show (default: 10).
.PARAMETER DryRun
    If set, simulate status query without querying the system.
.EXAMPLE
    .\show-pywin32-service-status.ps1
    .\show-pywin32-service-status.ps1 -Tail 30 -DryRun
#>
param(
    [int]$Tail = 10,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if ($DryRun) {
    python -m ai_local.cli service status --dry-run --strategy pywin32
    exit $LASTEXITCODE
}

Write-Host "===== pywin32 Service Status ====="
python -m ai_local.cli service status --strategy pywin32
Write-Host "`n===== Recent log lines (tail=$Tail) ====="
python -m ai_local.cli service logs --tail $Tail
