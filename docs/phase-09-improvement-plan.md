# Phase 09 Improvement Plan

Phase 9 starts as an improvement and assessment phase. The immediate goal is not
to add broad new capability, but to make end-to-end output, integration stress,
noise, conflict, and no-path behavior measurable across the modules already
implemented in Phases 1-8.

## Current Functional Coverage

| Area | Implemented runtime coverage | Gate coverage |
| --- | --- | --- |
| Gateway and request lifecycle | Task intake, state reads, run records, decision state, audit-oriented lifecycle | request lifecycle, operational safety, thread control |
| Agent loop and planner | Plan generation, plan gate, retrieval handoff, evaluation routing, skill runtime handoff | agent loop, decision, confirmation, prompt injection |
| Patch pipeline | Patch objective, scope, size, risk, semantic review, ordered pre/post apply stages, rollback/retry/accept | big/small, patch levels, patch pipeline, conflict path |
| Evaluation gate | Score model, evidence readiness, retry budget, verification, confirmation, route audit | evaluation, decision, confirmation, evidence rank |
| Retrieval and indexer | Ripgrep/FTS/vector adapter boundary, stale row cleanup, maintenance commands, retrieval decision coupling | retrieval, flow memory rating, memory SQL |
| Knowledge and memory | Evidence ranking, conflict-aware knowledge use, memory write/read governance, regression matching | knowledge, memory layers, memory governance, memory regression |
| Tools and skills | Tool registry, web search tool boundary, package trust, installer, registry, script sandbox, runner, evidence handoff | tool combo, skills, operational safety, prompt injection |
| Integration pipeline | New `IntegratedDeveloperPipeline` threads plan, retrieval, skill runtime, evidence rank, patch decision, and structured output | `tests/test_integration_pipeline.py` |

## Non-Functional Coverage

| Non-functional | Current status | Remaining improvement |
| --- | --- | --- |
| Safety | Deny-by-default tools, approval gates, prompt-injection quarantine, rollback routes | Add more real process isolation after subprocess wrapper |
| Auditability | In-memory audit events for tool, evaluation, skill install/run, evidence refs | Persist end-to-end audit chains across SQLite stores |
| Determinism | Harnesses use fixed configs and deterministic fake contexts/tools | Add replay fixtures for full request lifecycle |
| Maintainability | Functional registry maps sprints to focused gates | Add one global integration gate registry entry for Phase 9 |
| Observability | Structured integration result exposes stages, reasons, evidence refs, risk flags | Add CLI report command for machine-readable pipeline output |
| Scalability | SQLite queue, retrieval/index maintenance, bounded subprocess timeouts | Add load/stress gates for queue worker and retriever indexes |

## Noise, Conflict, And Hop Depth

Implemented harness surfaces already cover:

- noise: mixed English/Vietnamese retrieval, SEO noise, weak evidence, prompt injection
- conflict: forced choice, no path, multi-instance disagreement, memory conflict
- hop depth: memory up to 20, core agent and extreme patch gates up to 50
- deep safety: policy shadowing, laundering evidence through skill/tool output, unsafe tool requests

Phase 9 should concentrate on output confidence rather than adding more isolated
module tests. The new integration pipeline gives one measurable result:

```text
task -> plan -> retrieval -> skill runtime -> evidence rank -> patch pipeline -> decision/output
```

The output contract records:

- `status` and `final_state`
- ordered `stages`
- `evidence_refs`
- `risk_flags`
- `reasons`
- `hop_depth`, `noise_profile`, and `conflict_profile`
- nested plan, skill, and patch decisions

## Initial Phase 9 Gate Set

| Gate | Purpose | Expected output |
| --- | --- | --- |
| `integration-output-ready` | Happy path with bilingual noise, ranked skill evidence, and patch accept | `status=done`, `final_state=DECISION_GATE`, audit evidence refs present |
| `integration-no-path-conflict` | Deep no-path conflict after retry budget | `status=rollback`, `final_state=ROLLBACK`, budget reason present |
| `integration-prompt-injection` | Retrieval prompt injection before skill execution | `status=quarantine`, no skill or patch execution |
| `global-developer` | Ensure all functional IDs remain mapped to gates | pass |
| `developer-sprints` | Ensure sprint registry remains complete | pass |
| `harness-regression` | Ensure all focused harness tests still pass together | pass |
| `quality` | Ruff and mypy static gates | pass |

## Objective Assessment

The project is functionally broad and has strong harness-first coverage. It has
runtime implementations for each planned module family and cross-module gates
for the most important risk classes. The main gap before Phase 9 was that
integration output was distributed across module tests; there was no single
result object proving the full runtime route and final output state.

The new pipeline closes that measurement gap at a small scale. It is still not a
production orchestrator. It is an integration harness runtime that should drive
Phase 9 improvements around output quality, persisted audit chains, replay, and
stress tests.

## Subjective Assessment

The architecture is now mature enough to continue, but Phase 9 should be
disciplined. Adding more modules would lower clarity. The next useful work is to
make the existing system easier to prove: one CLI command for global integration
output, persisted evidence chains, and replayable conflict/noise scenarios.

## Phase 9 Sprint Proposal

| Sprint | Focus | Gate requirement |
| --- | --- | --- |
| Sprint 01 | Integration output CLI and JSON report | integration output, global developer, ruff, mypy |
| Sprint 02 | Persist end-to-end evidence/audit chain in SQLite | memory SQL, evidence rank, request lifecycle |
| Sprint 03 | Replay fixtures for noise/conflict/no-path scenarios | noise, conflict path, multi-conflict |
| Sprint 04 | Stress gates for retriever, queue, and worker timeout behavior | retrieval, operational safety, thread control |
| Sprint 05 | Phase 9 close report and full cross-phase regression | full pytest, promote, global developer |
