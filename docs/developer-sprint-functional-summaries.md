# Developer Sprint Functional Summaries

| Functional | Before gate summary | After gate summary |
| --- | --- | --- |
| `F-CORE-001` | Scope the gateway lifecycle state and request evidence before code changes. | Report whether lifecycle and operational gates preserve create, ask, retry, stop, and audit branches. |
| `F-CORE-002` | Name the agent loop transition and decision branch touched by the patch. | Report whether agent-loop and decision gates still promote the changed transition. |
| `F-CORE-003` | State tool allowlist surface, observation expectation, and untrusted input risk. | Report whether tool and prompt-injection gates kept unsafe authorization blocked. |
| `F-CORE-004` | State lock, queue, outbox, crash, replay, or idempotency risk. | Report whether thread and operational gates preserved concurrency and recovery behavior. |
| `F-RET-001` | State query shape, context package, noise, and decision coupling risk. | Report whether retrieval and flow-aware memory gates retained scoped evidence selection. |
| `F-RET-002` | State index metadata and schema fields required by retrieval. | Report whether retrieval and SQL-linked gates preserve stored context inputs. |
| `F-HAR-001` | State patch size, evidence, checks, and target promotion level. | Report whether big, small, and patch-level gates enforce the same patch boundaries. |
| `F-HAR-002` | State objective, evidence chain, rollback condition, and conflict class. | Report whether patch pipeline and conflict gates still pick only valid paths. |
| `F-EVAL-001` | State score fields, risk threshold, retry budget, and confirmation trigger. | Report whether evaluator, decision, and confirmation gates route correctly. |
| `F-KNOW-001` | State knowledge level, evidence authority, rank impact, and expected conflict behavior. | Report whether knowledge, rank, and conflict gates avoid unsupported facts. |
| `F-KNOW-002` | State memory scope, evidence, freshness, conflict, and deep-hop risk. | Report whether memory gates preserve write, retrieval, governance, and regression behavior. |
| `F-SKILL-001` | State skill trust, allowed tools, module bridge, and workflow evidence. | Report whether skill and tool gates preserve permission-aware integration. |
