<#
.SYNOPSIS
    Show AI Local backend service status, recent logs, and runtime overview.

.DESCRIPTION
    Runs three commands to give a complete picture:
    1. python -m ai_local.cli service status --workspace <workspace>
    2. python -m ai_local.cli service logs --workspace <workspace> --tail <Tail>
    3. python -m ai_local.cli runtime status --workspace <workspace>

.PARAMETER Workspace
    Path to the AI Local workspace (required).

.PARAMETER Tail
    Number of recent log lines to show. Default 30.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [int]$Tail = 30
)

$resolvedWs = (Resolve-Path -Path $Workspace -ErrorAction SilentlyContinue).Path
if (-not $resolvedWs) {
    Write-Error "Workspace path does not exist: $Workspace"
    exit 1
}

$pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Error "Python not found on PATH."
    exit 1
}
$PythonExe = $pyCmd.Source

# 1. Service status
Write-Output "========================================"
Write-Output "  SERVICE STATUS"
Write-Output "========================================"
& $PythonExe -m ai_local.cli service status --workspace $resolvedWs
Write-Output ""

# 2. Recent logs
Write-Output "========================================"
Write-Output "  RECENT LOGS (--tail $Tail)"
Write-Output "========================================"
& $PythonExe -m ai_local.cli service logs --workspace $resolvedWs --tail $Tail
Write-Output ""

# 3. Runtime status
Write-Output "========================================"
Write-Output "  RUNTIME STATUS"
Write-Output "========================================"
& $PythonExe -m ai_local.cli runtime status --workspace $resolvedWs
Write-Output ""
