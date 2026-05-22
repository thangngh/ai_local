# AI Infrastructure Project

Local AI infrastructure project built with Python and FastAPI.

## Scope

This repository defines an MVP foundation for a local AI agent runtime:

- Gateway API
- Agent loop
- Planner
- Evaluator
- Knowledge harness
- Memory system
- SQLite-backed queue worker
- Outbox dispatcher
- Tool registry
- Retriever
- Indexer MVP

## Stack

- API: Python, FastAPI
- DB: SQLite, SQLAlchemy Core/ORM
- Queue: lightweight SQLite-backed queue
- Worker: Python asyncio, process pool when needed
- Tool runner: subprocess with timeout and allowlist
- Retrieval: ripgrep subprocess, SQLite FTS5, sqlite-vec, tree-sitter
- Config: YAML plus Pydantic Settings
- CLI: Typer
- Testing and quality: pytest, ruff, mypy

## Documents

- [Requirements](docs/requirements.md)
- [Requirement Sources](docs/requirement-sources.md)
- [Requirements to Harness Pipeline](docs/requirements-to-harness.md)
- [Skills](docs/skills.md)
- [Tools](docs/tools.md)
- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Noise Harness](docs/noise-harness.md)
- [Memory Regression Harness](docs/memory-regression-harness.md)
- [Memory Layer Harness](docs/memory-layer-harness.md)
- [Composite Gates](docs/composite-gates.md)
- [Decision Harness](docs/decision-harness.md)
- [Retrieval Harness](docs/retrieval-harness.md)
- [Agent Loop Harness](docs/agent-loop-harness.md)
- [Big and Small Harness](docs/big-small-harness.md)
- [Patch Pipeline Harness](docs/patch-pipeline-harness.md)
- [Patch Levels](docs/patch-levels.md)
- [Evaluation Gate Harness](docs/evaluation-gate-harness.md)
- [Confirmation Flow Harness](docs/confirmation-flow-harness.md)
- [Knowledge Harness Gate](docs/knowledge-harness-gate.md)
- [Evidence + Rank Gate](docs/evidence-rank-gate.md)
- [Web Search Tool](docs/web-search-tool.md)
- [Skills Harness](docs/skills-harness.md)
- [Memory + SQL Gate](docs/memory-sql-gate.md)
- [Conflict Path Gate](docs/conflict-path-gate.md)
- [Multi-Instance Conflict Gate](docs/multi-instance-conflict-gate.md)
- [Request Lifecycle Gate](docs/request-lifecycle-gate.md)
- [Prompt Injection Refusal Gate](docs/prompt-injection-refusal-gate.md)
- [Thread Control Gate](docs/thread-control-gate.md)
- [Operational Safety Gate](docs/operational-safety-gate.md)
- [Memory Governance Gate](docs/memory-governance-gate.md)
- [Flow Memory Rating Gate](docs/flow-memory-rating-gate.md)
- [Global Developer Harness](docs/global-developer-harness.md)
- [Gate Harness Summary](docs/gate-harness-summary.md)
- [Developer Phase Report](docs/developer-phase-report.md)
- [Developer Sprint Plan](docs/developer-sprint-plan.md)
- [Developer Sprint Functional Summaries](docs/developer-sprint-functional-summaries.md)
- [Sprint 01 Progress](docs/sprint-01-progress.md)
- [Sprint 02 Progress](docs/sprint-02-progress.md)
- [Sprint 03 Progress](docs/sprint-03-progress.md)
- [Sprint 04 Progress](docs/sprint-04-progress.md)
- [Sprint 05 Progress](docs/sprint-05-progress.md)
- [Sprint 06 Progress](docs/sprint-06-progress.md)
- [Sprint 07 Progress](docs/sprint-07-progress.md)
- [Sprint 08 Progress](docs/sprint-08-progress.md)
- [Phase 02 Sprint 01 Progress](docs/phase-02-sprint-01-progress.md)
- [Phase 02 Sprint 02 Progress](docs/phase-02-sprint-02-progress.md)
- [Phase 02 Sprint 03 Progress](docs/phase-02-sprint-03-progress.md)
- [Phase 02 Sprint 04 Progress](docs/phase-02-sprint-04-progress.md)
- [Phase 02 Sprint 05 Progress](docs/phase-02-sprint-05-progress.md)
- [Phase 02 Sprint 06 Progress](docs/phase-02-sprint-06-progress.md)
- [Phase 02 Sprint 07 Progress](docs/phase-02-sprint-07-progress.md)
- [Phase 02 Sprint 08 Progress](docs/phase-02-sprint-08-progress.md)
- [Phase 02 Sprint 09 Progress](docs/phase-02-sprint-09-progress.md)
- [Phase 03 Sprint 01 Progress](docs/phase-03-sprint-01-progress.md)
- [Phase 03 Sprint 02 Progress](docs/phase-03-sprint-02-progress.md)
- [Phase 03 Sprint 03 Progress](docs/phase-03-sprint-03-progress.md)
- [Phase 03 Sprint 04 Progress](docs/phase-03-sprint-04-progress.md)
- [Phase 03 Sprint 05 Progress](docs/phase-03-sprint-05-progress.md)
- [Phase 03 Close Report](docs/phase-03-close-report.md)
- [Phase 04 Sprint 01 Progress](docs/phase-04-sprint-01-progress.md)
- [Phase 04 Sprint 02 Progress](docs/phase-04-sprint-02-progress.md)
- [Phase 04 Sprint 03 Progress](docs/phase-04-sprint-03-progress.md)
- [Phase 04 Sprint 04 Progress](docs/phase-04-sprint-04-progress.md)
- [Phase 04 Sprint 05 Progress](docs/phase-04-sprint-05-progress.md)
- [Phase 04 Close Report](docs/phase-04-close-report.md)
- [Phase 05 Entry Plan](docs/phase-05-entry-plan.md)
- [Phase 05 Close Checklist](docs/phase-05-close-checklist.md)

## Development Rule

Development is requirements-first:

1. Fetch requirement sources from [AI Infranstructure](https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e) and its configured sub pages.
2. Normalize into acceptance criteria.
3. Generate and review the harness test.
4. Implement only after the harness is accepted.
5. Run the harness, evaluate evidence, and pass the decision gate.

Machine-readable registries:

- [configs/skills.yaml](configs/skills.yaml)
- [configs/tools.yaml](configs/tools.yaml)
