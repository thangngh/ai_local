# Developer Phase Report

Source processed on this pass:

- Main Notion page: `AI Infranstructure`
- Source role: architecture baseline and MVP phase order

## Phase Order

| Phase | Focus | Functional output |
| --- | --- | --- |
| Phase 1 | Core loop | Gateway, agent loop, task flow, tool registry, audit baseline |
| Phase 2 | Retrieval | Indexer, parser, FTS5, sqlite-vec, context builder |
| Phase 3 | Harness | Big harness, patch harness, scope/diff/test/rollback gates |
| Phase 4 | Evaluation | Evaluator JSON, score/rank, decision, confirmation |
| Phase 5 | Knowledge | Knowledge DB, evidence store, ranker, conflict resolver, claim verifier |
| Phase 6 | Skills | Skill loader, registry, scripts, permission integration |

## Functional Requirements

Every developer functional item is mapped to gate harness coverage in
`configs/global_developer_harness.yaml`.

| Group | Functional requirement | Gate coverage |
| --- | --- | --- |
| Core | FastAPI Gateway and request lifecycle | `request_lifecycle`, `operational_safety` |
| Core | Agent loop state machine and planner flow | `agent_loop`, `decision` |
| Core | Tool registry and tool execution | `tool_combo`, `prompt_injection` |
| Core | Queue worker, thread control, outbox dispatcher | `thread_control`, `operational_safety` |
| Retrieval | Hybrid retrieval and context package | `retrieval`, `flow_memory_rating` |
| Retrieval | Indexer MVP inputs | `retrieval`, `memory_sql` |
| Harness | Big/small patch harness and patch levels | `big_harness`, `small_patch`, `patch_levels` |
| Harness | Patch pipeline, evidence, rollback path | `patch_pipeline`, `composite`, `conflict_paths` |
| Evaluation | Evaluation, decision, confirmation | `evaluation`, `decision`, `confirmation` |
| Knowledge | Knowledge rank and conflict resolution | `knowledge`, `evidence_rank`, `multi_conflict` |
| Knowledge | Memory layers and governance | `memory_layers`, `memory_sql`, `memory_governance`, `memory_regression` |
| Skills | Skill loader and workflow integration | `skills`, `tool_combo` |

## Non-Functional Requirements

| Area | Non-functional requirement | Gate coverage |
| --- | --- | --- |
| Safety | Retrieved content cannot become policy | `noise`, `prompt_injection`, `operational_safety` |
| Safety | Risky actions confirm, ask, or stop | `confirmation`, `decision`, `conflict_paths` |
| Quality | Evidence and tests gate confident claims | `evidence_rank`, `evaluation`, `patch_pipeline` |
| Quality | Small patches promote by risk and depth | `small_patch`, `patch_levels`, `composite` |
| Local-first | SQLite and audit-oriented flow stay explicit | `memory_sql`, `operational_safety`, `request_lifecycle` |
| Robustness | Deep-hop noise and conflict avoid false certainty | `noise`, `multi_conflict`, `flow_memory_rating` |

## Developer Decision

The project is ready to move from harness-first scaffolding into phase developer
work in this order:

1. Implement the Phase 1 core loop behind the existing request, agent-loop,
   tool, thread, and operational safety gates.
2. Keep retrieval/indexer work in Phase 2 bounded by retrieval and context
   coverage before widening memory injection.
3. Treat the global harness as a coverage gate for phase planning. Focused
   harnesses remain the execution gates for each patch.
