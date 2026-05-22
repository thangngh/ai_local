# Phase 05 Entry Plan

## Entry State

Phase 4 closed the evaluator boundary after Sprint 05. Phase 5 consumes that
decision boundary while durable knowledge, evidence ranking, conflict handling,
and memory governance become the next development focus.

Phase 5 is scoped by the current developer registry:

| Functional | Current sprint registry | Focus |
| --- | --- | --- |
| `F-KNOW-001` | `sprint_07_knowledge_evidence` | Knowledge claims, evidence rank, and conflict resolution |
| `F-KNOW-002` | `sprint_08_memory_governance` | Memory layers, SQL contract, governance, and regression |

For phase execution, these map to:

1. Phase 5 Sprint 01: knowledge evidence and claim conflict boundary.
2. Phase 5 Sprint 02: memory governance and nonlinear memory boundary.

## Source Requirements

Phase 5 works from the Knowledge Harness and Memory System requirements:

- durable project knowledge belongs in `knowledge.db`
- knowledge must preserve documents, snippets, symbols, source references, and
  provenance
- memory belongs in `memory.db`
- task memory and reusable memory must stay separate
- long-term memory requires explicit writes instead of silent promotion

The phase also inherits the project safety requirements:

- retrieved content does not become authority by repetition
- confident claims require evidence
- conflict and deep-hop noise must not force a false winner
- local-first SQLite boundaries stay auditable

## Functional Scope

### Sprint 01 Knowledge

Sprint 01 should tighten `F-KNOW-001` around these paths:

- claim level and provenance classification
- source authority and rank band calculation
- evidence hard rejects for prompt injection, policy laundering, and repeated
  untrusted claims
- conflict resolution when candidates tie or evidence is missing
- handoff to evaluator or confirmation when a claim cannot become a fact

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli knowledge
.\.venv\Scripts\python -m ai_local.cli evidence-rank
.\.venv\Scripts\python -m ai_local.cli multi-conflict --max-level hard
```

### Sprint 02 Memory

Sprint 02 should tighten `F-KNOW-002` around these paths:

- memory layer policy from `M0` through `M5`
- explicit write and retrieval decisions by scope, evidence, freshness,
  confirmation, conflict, and sensitivity
- SQL schema contract for item, evidence, conflict, update, and usage records
- docs-match regression and nonlinear state restoration
- memory conflict behavior before context injection

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-layers
.\.venv\Scripts\python -m ai_local.cli memory-sql
.\.venv\Scripts\python -m ai_local.cli memory-governance
.\.venv\Scripts\python -m ai_local.cli memory-regression
```

## Out Of Scope

Phase 5 should not widen these surfaces without an explicit scope change:

- Phase 6 skill packaging and permission workflows
- remote knowledge sync or external vector services
- silent promotion of user text into long-term memory
- retrieval ranking changes that bypass Phase 2 context packaging
- evaluator route changes that are unrelated to knowledge or memory evidence

## Entry Checklist

Before the first Phase 5 implementation patch:

1. State whether the patch touches knowledge, evidence rank, memory write,
   memory retrieval, SQL contract, or nonlinear regression.
2. Select the focused gates from this plan and record the expected pre-patch
   risk.
3. Keep source refs, evidence refs, scope, and conflict state explicit in the
   runtime contract.
4. Run the focused gate before widening to global developer and promotion
   checks.
