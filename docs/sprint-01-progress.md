# Sprint 01 Progress

Sprint focus:

- `F-CORE-001`: FastAPI Gateway and request lifecycle
- `F-CORE-002`: Agent loop state machine and planner flow

## Patch 01

### Functional `F-CORE-001`

Before gate summary:

The first gateway patch only opens the request intake path. It creates a task
identifier, keeps the request status at `pending`, and enqueues an `agent_run`
job carrying the goal and project context before wider lifecycle persistence is
introduced.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level medium
```

After gate summary:

Request lifecycle gates passed through extreme lifecycle cases and operational
safety passed through medium queue/outbox coverage. The intake patch keeps job
creation inside a typed gateway helper while the endpoint delegates to it.

### Functional `F-CORE-002`

Before gate summary:

The first loop patch replaces the stub result with one planned step from the
task goal. The planner trims the goal and records `requirements.extract` as the
initial tool dependency before deeper state transitions are implemented.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level medium
.\.venv\Scripts\python -m ai_local.cli decision --max-level medium
```

After gate summary:

Agent-loop and decision gates passed through medium coverage. The production loop
now exposes an initial planned result, which gives the next Sprint 01 patch a
concrete state to extend into retrieval and plan-gate behavior.

## Patch 02

### Functional `F-CORE-001`

Before gate summary:

The second gateway patch introduces a run record behind task intake. It keeps
state local and explicit first: intake writes a pending run into an in-memory
store, the queue receives the work item, and the read path reports the stored
task state before durable task DB work begins.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level medium
```

After gate summary:

Request lifecycle passed through extreme cases and operational safety passed
through medium coverage. The task read helper and gateway route now share the
same stored state record, so the next lifecycle patch can replace storage
without changing the intake contract.

### Functional `F-CORE-002`

Before gate summary:

The second loop patch makes planning a state transition instead of only a return
value. The loop can mark a stored run as planned and attach the initial plan
while preserving the existing planner boundary.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level medium
.\.venv\Scripts\python -m ai_local.cli decision --max-level medium
```

After gate summary:

Agent-loop and decision gates passed through medium coverage. The stored run now
transitions from pending to planned after the loop prepares the first plan,
which leaves plan-gate work isolated for the next patch.

## Patch 03

### Functional `F-CORE-001`

Before gate summary:

The final Sprint 01 gateway patch extends the read contract from raw status into
plan-gate lifecycle state. A task read now exposes the stored decision, next
state, and initial plan without pulling retrieval or tool work into the core
intake boundary.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level medium
```

After gate summary:

Lifecycle and operational focused gates passed. Gateway intake now creates a
pending run record, queues the agent run, and exposes the first lifecycle state
after planning through the same stored run record.

### Functional `F-CORE-002`

Before gate summary:

The final Sprint 01 loop patch adds the plan gate boundary required by the main
loop flow. Explicit plan signals separate accepted plans from ambiguous and
unsafe plans before retrieval work starts.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level medium
.\.venv\Scripts\python -m ai_local.cli decision --max-level medium
```

After gate summary:

Agent-loop and decision focused gates passed. The production loop now records
the `continue -> RETRIEVE`, `ask_user -> ASK_USER`, and `stop -> STOP` plan-gate
branches and updates run state to planned, waiting-user, or stopped.

## Sprint 01 Exit

Sprint 01 core patching is complete for the current MVP boundary:

- Gateway task intake creates a queued run and exposes current run state.
- Agent run state tracks pending, planned, waiting-user, and stopped branches.
- Planner emits the first requirement-analysis plan.
- Plan gate controls the handoff from plan into retrieval or human/stop paths.

Sprint 02 can take tool runtime, queue worker behavior, thread control, and
outbox execution without widening the Sprint 01 boundary further.
