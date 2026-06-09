<#
.SYNOPSIS
    Guarded wrapper for uninstalling the AI Local backend Windows service.

.DESCRIPTION
    Runs: python -m ai_local.cli service uninstall --workspace <workspace>
    Does NOT delete workspace data by default.

.PARAMETER Workspace
    Path to the AI Local workspace (required).

.PARAMETER DryRun
    If set, runs the uninstall command with --dry-run (no side effects).

.PARAMETER RemoveLogs
    If set, removes .ai-local/logs/*.log files after uninstall.
    Does NOT remove reports, backups, or databases.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [switch]$DryRun,

    [switch]$RemoveLogs
)

$resolvedWs = (Resolve-Path -Path $Workspace -ErrorAction SilentlyContinue).Path
if (-not $resolvedWs) {
    Write-Error "Workspace path does not exist: $Workspace"
    exit 1
}

if ($RemoveLogs) {
    Write-Warning "WARNING: -RemoveLogs is set. Log files will be deleted."
    Write-Warning "Reports, backups, and databases will NOT be removed."
    $logsDir = Join-Path -Path $resolvedWs -ChildPath ".ai-local\logs"
    if (Test-Path -LiteralPath $logsDir -PathType Container) {
        $logFiles = Get-ChildItem -Path $logsDir -Filter "*.log"
        if ($logFiles) {
            Write-Output "The following log files will be removed:"
            foreach ($f in $logFiles) {
                Write-Output "  $($f.FullName)"
            }
        } else {
            Write-Output "No log files found in $logsDir"
        }
    }
    if (-not $DryRun) {
        Write-Output ""
        $confirm = Read-Host "Type YES to confirm log removal"
        if ($confirm -ne "YES") {
            Write-Output "Log removal cancelled."
            exit 0
        }
    }
}

# CLI command
$cliArgs = @("-m", "ai_local.cli", "service", "uninstall", "--workspace", $resolvedWs)
if ($DryRun) {
    $cliArgs += "--dry-run"
}

$pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Error "Python not found on PATH."
    exit 1
}
$PythonExe = $pyCmd.Source

Write-Output "Running: $PythonExe $($cliArgs -join ' ')"
Write-Output ""
& $PythonExe $cliArgs
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0 -and $RemoveLogs -and -not $DryRun) {
    $logsDir = Join-Path -Path $resolvedWs -ChildPath ".ai-local\logs"
    if (Test-Path -LiteralPath $logsDir -PathType Container) {
        Remove-Item -Path "$logsDir\*.log" -Force
        Write-Output "Log files removed from $logsDir"
    }
}

if ($exitCode -eq 0) {
    Write-Output ""
    Write-Output "Service uninstalled."
    Write-Output "Workspace data at $resolvedWs was preserved."
} else {
    Write-Output ""
    Write-Error "Service uninstall failed (exit $exitCode)."
}

exit $exitCode
