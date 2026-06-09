<#
.SYNOPSIS
    Stop then start the AI Local backend Windows service.

.DESCRIPTION
    Runs: python -m ai_local.cli service stop --workspace <workspace>
    Then: python -m ai_local.cli service start --workspace <workspace>

.PARAMETER Workspace
    Path to the AI Local workspace (required).

.PARAMETER DryRun
    If set, runs both commands with --dry-run (no side effects).
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [switch]$DryRun
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

# Stop
$stopArgs = @("-m", "ai_local.cli", "service", "stop", "--workspace", $resolvedWs)
if ($DryRun) { $stopArgs += "--dry-run" }
Write-Output "=== Stop service ==="
Write-Output "Running: $PythonExe $($stopArgs -join ' ')"
Write-Output ""
& $PythonExe $stopArgs
if ($LASTEXITCODE -ne 0 -and -not $DryRun) {
    Write-Error "Stop failed (exit $LASTEXITCODE). Aborting restart."
    exit $LASTEXITCODE
}
Write-Output ""

# Start
$startArgs = @("-m", "ai_local.cli", "service", "start", "--workspace", $resolvedWs)
if ($DryRun) { $startArgs += "--dry-run" }
Write-Output "=== Start service ==="
Write-Output "Running: $PythonExe $($startArgs -join ' ')"
Write-Output ""
& $PythonExe $startArgs
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Error "Start failed (exit $exitCode)."
}
Write-Output ""

if ($exitCode -eq 0) {
    Write-Output "Service restarted."
}

exit $exitCode
