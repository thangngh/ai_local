<#
.SYNOPSIS
    Detect NSSM (Non-Sucking Service Manager) on the current machine.

.DESCRIPTION
    Checks $env:NSSM_EXE first, then looks for nssm.exe on PATH.
    Exits 0 if found, non-zero if missing.
#>

$found = $null

# 1. Check NSSM_EXE environment variable
$nssmExe = [Environment]::GetEnvironmentVariable("NSSM_EXE")
if ($nssmExe) {
    if (Test-Path -LiteralPath $nssmExe -PathType Leaf) {
        $found = $nssmExe
    }
}

# 2. Check PATH
if (-not $found) {
    $pathCandidates = @("nssm.exe", "nssm")
    foreach ($name in $pathCandidates) {
        $resolved = Get-Command $name -ErrorAction SilentlyContinue
        if ($resolved) {
            $found = $resolved.Source
            break
        }
    }
}

if ($found) {
    Write-Output "NSSM found"
    Write-Output "PATH $found"
    exit 0
} else {
    Write-Output "NSSM missing"
    Write-Output "HINT install NSSM manually and set NSSM_EXE or add nssm.exe to PATH"
    exit 1
}
