param(
    [switch]$SkipModelCompare,
    [switch]$WithOllamaGolden
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$GateConfig = Join-Path $Root "configs\benchmark_release_gate.yaml"

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

$benchArgs = @(
    "-m", "ai_local.cli", "benchmark-run",
    "--output", ".reports/benchmark/latest.json",
    "--enforce-thresholds",
    "--enforce-history",
    "--skip-dashboard"
)
if ($WithOllamaGolden) {
    $benchArgs += "--with-ollama"
}
Invoke-Step "benchmark-golden" $benchArgs

Invoke-Step "benchmark-adversarial" @(
    "-m", "ai_local.cli", "benchmark-run",
    "--with-adversarial",
    "--output", ".reports/benchmark/adversarial_latest.json",
    "--enforce-thresholds",
    "--enforce-history",
    "--skip-dashboard"
)

Invoke-Step "benchmark-ollama-check" @("-m", "ai_local.cli", "benchmark-ollama-check")
Invoke-Step "benchmark-adversarial-ollama" @(
    "-m", "ai_local.cli", "benchmark-run",
    "--with-adversarial",
    "--with-ollama",
    "--output", ".reports/benchmark/adversarial_ollama_latest.json",
    "--enforce-thresholds",
    "--enforce-history",
    "--skip-dashboard"
)

Invoke-Step "benchmark-regression-gate" @(
    "-m", "ai_local.cli", "benchmark-regression-gate",
    "--report", ".reports/benchmark/latest.json",
    "--pack", "golden"
)
Invoke-Step "benchmark-regression-adversarial" @(
    "-m", "ai_local.cli", "benchmark-regression-gate",
    "--report", ".reports/benchmark/adversarial_latest.json",
    "--pack", "golden+adversarial"
)

if (-not $SkipModelCompare) {
    Invoke-Step "benchmark-compare-models" @(
        "-m", "ai_local.cli", "benchmark-compare-models",
        "--skip-dashboard"
    )
}

Invoke-Step "benchmark-dashboard" @("-m", "ai_local.cli", "benchmark-dashboard")
Invoke-Step "benchmark-overall-summary" @("-m", "ai_local.cli", "benchmark-overall-summary")
Invoke-Step "benchmark-release-decision" @("-m", "ai_local.cli", "benchmark-release-decision")

Write-Host "PASS release-gate"
