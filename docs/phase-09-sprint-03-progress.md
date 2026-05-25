# Phase 09 Sprint 03 Progress

Implemented Phase 9 Sprint 03: replay fixtures for noise, conflict, and no-path
integration scenarios.

## Functional Scope

Sprint 03 turns Phase 9 report output into replayable regression fixtures. The
fixtures re-run deterministic integration scenarios and compare the resulting
status, final state, stages, evidence, risk flags, hop depth, noise profile, and
conflict profile against expected values.

Implemented:

- `configs/phase9_replay_fixtures.yaml`
- `ai_local.pipeline.replay`
- CLI command `phase9-replay`
- replay tests for fixture coverage, pass/fail behavior, CLI output, and audit
  chain persistence

## Fixtures

Current fixture set:

| Fixture | Scenario | Expected route |
| --- | --- | --- |
| `phase9_ready_output` | bilingual/noisy ready output | `done -> DECISION_GATE` |
| `phase9_no_path_rollback` | no-path conflict, hop depth 50 | `rollback -> ROLLBACK` |
| `phase9_prompt_injection_quarantine` | prompt injection retrieval noise | `quarantine -> QUARANTINE` |

## CLI Example

```powershell
.\.venv\Scripts\python -m ai_local.cli phase9-replay `
  --config configs\phase9_replay_fixtures.yaml `
  --workspace-root . `
  --patch-levels-config configs\patch_levels.yaml `
  --audit-db audit.db
```

The command prints one PASS/FAIL line per replay fixture and can persist one
audit chain per replayed scenario.

## Gate Harness

Focused gate:

```powershell
.\.venv\Scripts\python -m pytest tests/test_phase9_replay.py
```

Related cross-module gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli noise
.\.venv\Scripts\python -m ai_local.cli conflict-paths --max-level hard
.\.venv\Scripts\python -m ai_local.cli multi-conflict --max-level hard
.\.venv\Scripts\python -m ai_local.cli prompt-injection
```

## Assessment

Sprint 03 closes the replayability gap from the Phase 9 plan. The system now has
small deterministic replay fixtures for the three key output classes: ready,
conflicted no-path, and unsafe prompt injection. Later stress gates can use the
same fixture shape with larger project-index and queue-worker loads.
