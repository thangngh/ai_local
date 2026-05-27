# Benchmark release gate

The release gate is the fixed entrypoint before merge or tagged release. It runs harness gates, golden and adversarial benchmarks, history regression checks, optional Ollama model comparison, and writes a single dashboard artifact.

## Happy path (local)

```powershell
.\scripts\release-gate.ps1
.\.venv\Scripts\python -m ai_local.cli benchmark-dashboard
.\.venv\Scripts\python -m ai_local.cli benchmark-trend --last 10
```

Skip model comparison when Ollama is unavailable:

```powershell
.\scripts\release-gate.ps1 -SkipModelCompare
```

## Steps

1. `doctor` (skips Ollama and ripgrep probes for speed in CI)
2. `phase-fast-gate --clean`
3. `promote --max-level hard`
4. `benchmark-run --enforce-thresholds --enforce-history` → `.reports/benchmark/latest.json`
5. `benchmark-run --with-adversarial` → `.reports/benchmark/adversarial_latest.json`
6. `benchmark-regression-gate` for golden and adversarial packs
7. `benchmark-compare-models` (requires Ollama; skipped with `-SkipModelCompare`)
8. `benchmark-dashboard` → `.reports/benchmark/dashboard.md`
9. `benchmark-overall-summary` → `.reports/benchmark/overall_summary.md`
10. `benchmark-release-decision` → PASS / PASS_WITH_WARNINGS / BLOCK (exit 1 on BLOCK)

Adversarial + Ollama artifact: `.reports/benchmark/adversarial_ollama_latest.json`

Seed comparable history baselines (10+ runs per profile):

```powershell
.\.venv\Scripts\python -m ai_local.cli benchmark-seed-history --runs 10 --harness-only
.\.venv\Scripts\python -m ai_local.cli benchmark-seed-history --runs 10 --ollama-only
```

Configuration: `configs/benchmark_release_gate.yaml`.

## Self-hosted CI

Workflow: `.github/workflows/benchmark-release-gate.yml`

- Trigger: `workflow_dispatch` or push of tags `v*`
- Runner labels: `self-hosted`, `linux`, `ollama`
- Uploads: `dashboard.md`, `history.jsonl`, `comparison.md`, latest benchmark JSON files

PR validation remains fast in `.github/workflows/gate.yml` (harness-only).

## Adversarial pack

Golden tasks live under `golden_tasks/*/task.json` (22 tasks). Adversarial tasks live under `golden_tasks/adversarial/**/task.json` (~10 tasks) and are included only with `--with-adversarial`.

## Regression and thresholds

- Absolute thresholds: `configs/benchmark_thresholds.yaml` (`--enforce-thresholds`)
- History regression: `configs/benchmark_regression.yaml` (`--enforce-history` or `benchmark-regression-gate`)
- History entries include `pack`: `golden` or `golden+adversarial`
