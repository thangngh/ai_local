param(
    [switch]$WithOllama
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

function Invoke-Step {
    param(
        [string]$Label,
        [string[]]$Args
    )
    Write-Host "==> $Label"
    & $Python @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL $Label (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
}

Invoke-Step "doctor" @("-m", "ai_local.cli", "doctor", "--skip-ollama", "--skip-ripgrep")
Invoke-Step "phase-fast-gate" @(
    "-m", "ai_local.cli", "phase-fast-gate",
    "--clean",
    "--output", ".reports/phase-fast-gate/latest.json"
)
Invoke-Step "promote" @("-m", "ai_local.cli", "promote", "--max-level", "hard")
Invoke-Step "benchmark-run" @(
    "-m", "ai_local.cli", "benchmark-run",
    "--output", ".reports/benchmark/latest.json",
    "--enforce-thresholds"
)

if ($WithOllama) {
    Invoke-Step "benchmark-run-ollama" @(
        "-m", "ai_local.cli", "benchmark-run",
        "--with-ollama",
        "--output", ".reports/benchmark/ollama_latest.json",
        "--enforce-thresholds"
    )
}

Write-Host "PASS full-gate"
