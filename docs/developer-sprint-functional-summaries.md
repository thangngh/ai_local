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
| `F-HAR-003` | State patch evidence refs and evidence kinds. | Report whether accepted patch attempts keep evidence source binding explicit. |
| `F-HAR-004` | State required focused check IDs and test evidence. | Report whether required check results remain bound to accepted attempts. |
| `F-HAR-005` | State required pre-apply diff, scope, risk, and semantic stages. | Report whether patch writes remain behind ordered pre-apply gates. |
| `F-HAR-006` | State evaluator status and evaluator evidence before decision. | Report whether decision entry stays behind evaluator proof. |
| `F-HAR-007` | State focused test, test gate, and evaluator stages after apply. | Report whether post-apply stages stay ordered before accepted decisions. |
| `F-HAR-008` | State Big Harness safety, confirmation, retry limit, and exhausted retry outcome. | Report whether repeated unsafe patch retries ask or rollback. |
| `F-EVAL-001` | State score fields, risk threshold, retry budget, and confirmation trigger. | Report whether evaluator, decision, and confirmation gates route correctly. |
| `F-EVAL-002` | State evaluator context/test evidence, verification context, and audited quarantine or stop path. | Report whether evidence-gated accept and safety exit routing remain explicit. |
| `F-EVAL-003` | State agent-loop verification query, audit route, and memory or confirmation conflict boundary. | Report whether runtime verification adds context without promoting unresolved conflicts. |
| `F-EVAL-004` | State confirmation response, evaluator evidence, run-state resume, and conflicting confirmation reroute. | Report whether confirmation resumes evaluation without bypassing missing-evidence or ask-again routes. |
| `F-EVAL-005` | State tool observation status, empty output, repeated action count, finish evidence, and unsafe observation branch. | Report whether observation routing retries, verifies, re-plans, or finishes without false completion. |
| `F-KNOW-001` | State knowledge level, evidence authority, rank impact, and expected conflict behavior. | Report whether knowledge, rank, and conflict gates avoid unsupported facts. |
| `F-KNOW-002` | State memory scope, evidence, freshness, conflict, and deep-hop risk. | Report whether memory gates preserve write, retrieval, governance, and regression behavior. |
| `F-SKILL-001` | State skill trust, allowed tools, module bridge, and workflow evidence. | Report whether skill and tool gates preserve permission-aware integration. |
| `F-SKILL-002` | State package source ref, checksum, manifest identity, trust state, and deny-by-default branch. | Report whether package trust gates reject missing source, checksum, manifest, or trust policy. |
| `F-SKILL-003` | State script trust, declared tool permission, side-effect type, approval need, and audit fields. | Report whether script sandbox gates prevent side-effect, approval, patch, or evidence bypass. |
| `F-SKILL-004` | State discovery, manifest inspection, verification, controlled install root, rollback, and audit refs. | Report whether install/update lifecycle gates refuse malformed or policy-shadowing skills and preserve rollback evidence. |
| `F-SKILLRT-001` | State staging root, target root, atomic install, rollback artifact, malformed package refusal, and audit event. | Report whether controlled installer gates keep writes bounded and failed installs reversible. |
| `F-SKILLRT-002` | State installed package metadata, stale cleanup, index refresh, and lifecycle audit reference. | Report whether registry gates keep installed state aligned with disk and SQL metadata. |
| `F-SKILLRT-003` | State package trust, declared tool, subprocess command, cwd, timeout, side effect, approval, and output routing. | Report whether runner gates prevent allowlist, approval, timeout, patch, or evidence bypass. |
| `F-SKILLRT-004` | State event ids, package refs, script output refs, evidence kind, conflict class, and unsafe output routing. | Report whether audit and evidence gates keep skill output data-only until ranked. |
| `F-SKILLRT-005` | State selected skill, package state, script result, evidence refs, decision branch, retry or confirmation path, and rollback risk. | Report whether agent-loop gates integrate skill runtime without bypassing decisions or evidence. |
