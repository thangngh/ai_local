# Developer Sprint Plan

This plan cuts the developer phase into sprint-sized work while retaining the
main Notion phase order.

## Sprint Cuts

| Sprint | Phase | Functional IDs | Objective |
| --- | --- | --- | --- |
| Sprint 01 | Core loop | `F-CORE-001`, `F-CORE-002` | Request intake, lifecycle, agent loop, and planner decisions |
| Sprint 02 | Core loop | `F-CORE-003`, `F-CORE-004` | Tool runtime, queue, thread control, and outbox baseline |
| Sprint 03 | Retrieval | `F-RET-001`, `F-RET-002` | Retrieval packaging and indexer MVP inputs |
| Sprint 04 | Harness | `F-HAR-001`, `F-HAR-002` | Patch sizing, evidence, rollback, and harness promotion |
| Sprint 05 | Harness close | `F-HAR-003` to `F-HAR-008` | Evidence binding, stage trace, and retry budget closure |
| Phase 4 Sprint 01 | Evaluation | `F-EVAL-001` | Evaluator, decision gate, and confirmation flow |
| Phase 4 Sprint 02 | Evaluation | `F-EVAL-002` | Evidence payload, verify context, and audited safety routing |
| Phase 4 Sprint 03 | Evaluation | `F-EVAL-003` | Agent-loop verify runtime and conflict-safe evaluation routing |
| Phase 4 Sprint 04 | Evaluation | `F-EVAL-004` | Confirmation resume, run-state handoff, and evidence-safe rerouting |
| Phase 4 Sprint 05 | Evaluation | `F-EVAL-005` | Observation retry, re-plan, finish, and close routing |
| Sprint 07 | Knowledge | `F-KNOW-001` | Knowledge cards, evidence rank, and conflict resolver |
| Sprint 08 | Knowledge | `F-KNOW-002` | Memory layers, SQL, governance, and regression |
| Sprint 09 | Skills | `F-SKILL-001` | Skill loader and permission-aware tool integration |

## Functional Gate Work

| Functional | Gate harness tests |
| --- | --- |
| `F-CORE-001` | `request-lifecycle`, `operational-safety --max-level medium` |
| `F-CORE-002` | `agent-loop --max-level medium`, `decision --max-level medium` |
| `F-CORE-003` | `tool-combo --max-level medium`, `prompt-injection --max-level medium` |
| `F-CORE-004` | `thread-control`, `operational-safety` |
| `F-RET-001` | `retrieval`, `flow-memory-rating --max-level hard` |
| `F-RET-002` | `retrieval --max-level medium`, `memory-sql --max-level medium` |
| `F-HAR-001` | `big-harness`, `small-patch`, `patch-levels` |
| `F-HAR-002` | `patch-pipeline`, `composite`, `conflict-paths --max-level hard` |
| `F-HAR-003` | `small-patch`, `patch-pipeline`, `patch-levels` |
| `F-HAR-004` | `small-patch`, `patch-pipeline`, `patch-levels` |
| `F-HAR-005` | `patch-pipeline`, `composite`, `conflict-paths --max-level hard` |
| `F-HAR-006` | `patch-pipeline`, `composite`, `conflict-paths --max-level hard` |
| `F-HAR-007` | `patch-pipeline`, `small-patch`, `composite` |
| `F-HAR-008` | `big-harness`, `patch-pipeline`, `composite`, `conflict-paths --max-level hard` |
| `F-EVAL-001` | `evaluation`, `decision`, `confirmation` |
| `F-EVAL-002` | `evaluation`, `retrieval --max-level hard`, `patch-pipeline`, `operational-safety --max-level hard` |
| `F-EVAL-003` | `agent-loop --max-level hard`, `evaluation`, `flow-memory-rating --max-level hard`, `multi-conflict --max-level hard` |
| `F-EVAL-004` | `agent-loop --max-level hard`, `evaluation`, `confirmation --max-level hard`, `request-lifecycle` |
| `F-EVAL-005` | `agent-loop --max-level hard`, `evaluation`, `decision --max-level hard`, `operational-safety --max-level hard` |
| `F-KNOW-001` | `knowledge`, `evidence-rank`, `multi-conflict --max-level hard` |
| `F-KNOW-002` | `memory-layers`, `memory-sql`, `memory-governance`, `memory-regression` |
| `F-SKILL-001` | `skills`, `tool-combo --max-level hard` |

## Before And After Gate Summary

Each functional item has a required summary pair in
`configs/developer_sprints.yaml`.

Before running focused gates, the summary must state:

- which functional behavior is being changed
- which gate path is at risk
- which evidence, scope, or policy branch the patch touches

After running focused gates, the summary must state:

- which gate commands passed or failed
- which behavior was validated
- whether promotion can continue to broader harnesses

The sprint harness verifies that no functional item enters a sprint without
focused gate commands and these two summaries.
