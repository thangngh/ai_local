# Requirements

## Product Goal

Build a local AI infrastructure service that can plan, execute, evaluate, retrieve knowledge, persist memory, and safely run approved developer tools against local projects.

The MVP should be useful without external services. SQLite is the default persistence layer, subprocess tools are allowlisted, and the runtime should be observable through audit records.

## Functional Requirements

### Gateway API

- Expose FastAPI endpoints for task submission, task status, run logs, memory lookup, knowledge lookup, and tool registry inspection.
- Validate all inbound requests with Pydantic models.
- Return stable task IDs for asynchronous execution.
- Provide health and readiness endpoints.

### Agent Loop

- Load task context from `tasks.db`.
- Ask the planner for the next step.
- Dispatch tool calls through the tool registry.
- Persist observations, decisions, and final output.
- Stop on completion, cancellation, timeout, or max step count.

### Planner

- Convert a user goal into executable steps.
- Prefer deterministic local context before invoking expensive or risky actions.
- Produce structured plan items with intent, required tools, expected outputs, and risk level.

### Evaluator

- Score whether each step moved the task forward.
- Detect failed tool calls, empty outputs, repeated actions, and unsafe requests.
- Decide whether to retry, re-plan, request clarification, or finish.

### Knowledge Harness

- Store durable project knowledge in `knowledge.db`.
- Support documents, snippets, symbols, and source references.
- Track provenance for every indexed item.

### Memory System

- Store agent memory in `memory.db`.
- Separate short-lived task memory from reusable long-term memory.
- Support explicit writes only; do not silently promote arbitrary task text into long-term memory.

### Queue Worker

- Store pending, leased, completed, failed, and cancelled jobs in `tasks.db`.
- Use SQLite transactions for leasing work.
- Support retry count, visibility timeout, priority, and scheduled execution time.

### Outbox Dispatcher

- Store side effects in `metadata.db` or `tasks.db` outbox tables before execution.
- Dispatch notifications, callbacks, and deferred tool actions idempotently.
- Record dispatch attempts and failures.

### Tool Registry

- Define each tool with name, description, input schema, timeout, allowlist policy, and risk level.
- Reject unknown tools.
- Route shell tools through a constrained subprocess runner.

### Retriever

- Search local code and notes using ripgrep, SQLite FTS5, and vector search when available.
- Return source references with line numbers or document IDs.
- Rank exact lexical matches above speculative matches for code tasks.

### Indexer MVP

- Index project files, selected docs, and metadata into `knowledge.db`.
- Track file path, content hash, modified time, language, and extracted symbols.
- Re-index only changed files.

## Non-Functional Requirements

- Local-first: the core system must work without network access.
- Auditable: important state transitions and tool executions must be written to `audit.db`.
- Safe by default: subprocess execution requires explicit allowlist entries and timeouts.
- Modular: each runtime concern has a dedicated Python package.
- Testable: queue, registry, planner contracts, and subprocess safety require unit tests.
- Portable: run on Windows first, with Linux/macOS compatibility kept in mind.

## SQLite Databases

### `metadata.db`

- App metadata
- Runtime config snapshots
- Outbox events
- Schema version records

### `memory.db`

- Task memory
- Long-term memory
- Memory embeddings or references
- Memory provenance

### `knowledge.db`

- Documents
- Code chunks
- Symbols
- FTS5 indexes
- Optional sqlite-vec tables

### `tasks.db`

- Tasks
- Queue jobs
- Leases
- Step records
- Retry state

### `audit.db`

- API requests
- Tool executions
- Security decisions
- Worker lifecycle events
- Error records

## MVP Acceptance Criteria

- A user can submit a task through FastAPI and receive a task ID.
- A worker can lease and execute the task through the agent loop.
- The agent loop can call at least one safe local tool through the registry.
- Tool execution is audited with command, timeout, exit code, and captured output metadata.
- The retriever can search local files with ripgrep.
- The indexer can populate `knowledge.db` for a project directory.
- Tests cover queue leasing, tool allowlist rejection, and task lifecycle transitions.

