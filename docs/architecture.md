# Architecture

## Module Layout

Recommended Python package layout:

```text
ai_local/
  api/
    gateway.py
    schemas.py
  agent/
    loop.py
    state.py
  planner/
    service.py
    models.py
  evaluator/
    service.py
    models.py
  knowledge/
    harness.py
    models.py
    store.py
  memory/
    models.py
    store.py
  queue/
    models.py
    store.py
    worker.py
  outbox/
    dispatcher.py
    models.py
  tools/
    registry.py
    runner.py
    schemas.py
  retrieval/
    retriever.py
    fts.py
    ripgrep.py
  indexer/
    scanner.py
    symbols.py
  config/
    settings.py
  audit/
    store.py
  cli.py
```

## Runtime Flow

1. Gateway API receives a task request.
2. API validates input and inserts a task into `tasks.db`.
3. Queue worker leases the task.
4. Agent loop loads task state and relevant memory.
5. Planner emits the next action.
6. Tool registry validates the requested tool.
7. Runner executes the tool with timeout and audit logging.
8. Evaluator scores the observation.
9. Agent loop continues, re-plans, or completes the task.
10. Outbox dispatcher handles deferred side effects.

## Persistence Boundary

Use separate SQLite files to keep operational concerns isolated:

- `tasks.db` for active work and queue state
- `memory.db` for agent memory
- `knowledge.db` for retrieval and indexing
- `audit.db` for traceability
- `metadata.db` for runtime metadata and outbox events

## Migration Policy

Start with SQLAlchemy metadata creation for MVP tables. Introduce Alembic when:

- schema changes become frequent
- deployments need reversible migrations
- multiple developers or environments need synchronized upgrades
- data migrations become necessary

