# Phase 09 Sprint 04 Progress

Implemented Phase 9 Sprint 04: stress gates for retriever, queue, and worker
timeout behavior.

## Functional Scope

Sprint 04 adds deterministic stress gates around operational surfaces that are
important before Phase 9 close:

- retriever/indexer incremental load
- queue retry budget under mixed success/failure jobs
- worker timeout handling through retry and dead-letter routing

Implemented:

- `configs/phase9_stress_gates.yaml`
- `ai_local.pipeline.stress`
- CLI command `phase9-stress`
- stress tests for loader, runner, and CLI output

## Stress Cases

| Case | Surface | Expected result |
| --- | --- | --- |
| `phase9_retriever_incremental_load` | 32 indexed docs, second pass unchanged | `decision=continue`, hits selected |
| `phase9_queue_retry_budget` | 12 jobs, 4 failing, max attempts 2 | 8 succeeded, 4 dead-letter |
| `phase9_worker_timeout_dead_letter` | 3 timeout jobs, max attempts 2 | 3 dead-letter, timeout errors preserved |

## CLI Example

```powershell
.\.venv\Scripts\python -m ai_local.cli phase9-stress `
  --config configs\phase9_stress_gates.yaml `
  --workspace-root .phase9-stress
```

Example output:

```text
PASS phase9_retriever_incremental_load kind=retriever hop_depth=20 decision=continue first_indexed=32 second_unchanged=32 selected_hits=5
PASS phase9_queue_retry_budget kind=queue hop_depth=30 audit_events=16 dead_letter=4 pending=0 succeeded=8
PASS phase9_worker_timeout_dead_letter kind=worker_timeout hop_depth=50 audit_events=6 dead_letter=3 pending=0 succeeded=0 timeout_errors=3
```

## Gate Harness

Focused gate:

```powershell
.\.venv\Scripts\python -m pytest tests/test_phase9_stress.py
```

Related cross-module gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli retrieval
.\.venv\Scripts\python -m ai_local.cli operational-safety
.\.venv\Scripts\python -m ai_local.cli thread-control
```

## Assessment

Sprint 04 gives Phase 9 a lightweight operational stress layer without turning
the test suite into a slow load test. The cases are intentionally small,
deterministic, and CI-friendly while still covering index maintenance,
retry/dead-letter behavior, and timeout routing.
