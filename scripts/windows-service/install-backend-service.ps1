<#
.SYNOPSIS
    Guarded wrapper for installing the AI Local backend Windows service.

.DESCRIPTION
    Resolves workspace, checks prerequisites, and runs:
    python -m ai_local.cli service install --workspace <workspace>

.PARAMETER Workspace
    Path to the AI Local workspace (required).

.PARAMETER PythonExe
    Path to the Python interpreter. Defaults to (Get-Command python).Source.

.PARAMETER DryRun
    If set, runs the install command with --dry-run (no side effects).
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [Parameter(Mandatory = $false)]
    [string]$PythonExe,

    [switch]$DryRun
)

# Resolve workspace to absolute path
$resolvedWs = (Resolve-Path -Path $Workspace -ErrorAction SilentlyContinue).Path
if (-not $resolvedWs) {
    Write-Error "Workspace path does not exist: $Workspace"
    exit 1
}

# Check .ai-local directory
$aiLocalDir = Join-Path -Path $resolvedWs -ChildPath ".ai-local"
if (-not (Test-Path -LiteralPath $aiLocalDir -PathType Container)) {
    Write-Error "Workspace $resolvedWs has not been initialised."
    Write-Error "Run: python -m ai_local.cli init --workspace $resolvedWs"
    exit 1
}

# Resolve Python
if (-not $PythonExe) {
    $pyCmd = Get-Command "python" -ErrorAction SilentlyContinue
    if (-not $pyCmd) {
        Write-Error "Python not found on PATH. Specify -PythonExe."
        exit 1
    }
    $PythonExe = $pyCmd.Source
}

# Check NSSM unless dry-run
if (-not $DryRun) {
    & "$PSScriptRoot\check-nssm.ps1"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

# Print command
$cliArgs = @("-m", "ai_local.cli", "service", "install", "--workspace", $resolvedWs)
if ($DryRun) {
    $cliArgs += "--dry-run"
}
Write-Output "Running: $PythonExe $($cliArgs -join ' ')"
Write-Output ""

# Execute
& $PythonExe $cliArgs
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Output ""
    Write-Output "Service installed."
    Write-Output "Start it with: python -m ai_local.cli service start --workspace $resolvedWs"
} else {
    Write-Output ""
    Write-Error "Service install failed (exit $exitCode)."
}

exit $exitCode
