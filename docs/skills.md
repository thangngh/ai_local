# Skills

Skills are reusable workflows. In this project, development must start from requirements, then generate a harness test before code changes.

## Required Development Flow

```text
requirements.parse
-> requirements.normalize
-> harness.generate
-> harness.review
-> implementation.plan
-> patch.apply
-> harness.run
-> evaluator.score
-> decision.gate
```

No feature implementation should start until the requirement is converted into acceptance criteria and at least one harness test exists.

## Skill Contract

Each skill must define:

- `id`
- `purpose`
- `inputs`
- `outputs`
- `allowed_tools`
- `writes`
- `risk_level`
- `gates`
- `success_criteria`

## Core Skills

### `requirements.parse`

Purpose: parse raw requirement text, Notion content, tickets, or user prompts into structured requirement records.

Primary sources:

- https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e
- https://www.notion.so/365b38678ea581f1876ae3459ec1f686
- https://www.notion.so/365b38678ea581c2bbcbf79d42a9c1f2
- https://www.notion.so/366b38678ea581629d45fb6a245eacd9

Inputs:

- optional `source_urls`
- optional `source_text`
- optional `project_context`

Allowed tools:

- `notion.fetch`
- `requirements.extract`
- `knowledge.search`

Outputs:

- requirement ID
- goal
- actors
- constraints
- in-scope items
- out-of-scope items
- ambiguity list
- risk flags
- source evidence

Writes:

- `tasks.db.requirements`
- `knowledge.db.knowledge_items` for confirmed project facts

Gates:

- source URLs must default to the configured Notion requirement source set when not provided
- every requirement must keep a source reference
- ambiguous requirements must be marked, not guessed

Success criteria:

- requirement can be reviewed without reading the full source document

### `requirements.normalize`

Purpose: convert parsed requirements into acceptance criteria and testable behavior.

Inputs:

- `requirement_id`
- parsed requirement record

Allowed tools:

- `requirements.read`
- `acceptance_criteria.write`
- `knowledge.search`

Outputs:

- acceptance criteria
- negative cases
- invariants
- data setup requirements
- expected outputs

Writes:

- `tasks.db.acceptance_criteria`

Gates:

- each acceptance criterion must be observable
- each criterion must map to at least one harness test or explicit manual gate

Success criteria:

- no acceptance criterion depends only on model judgment

### `harness.generate`

Purpose: generate the test harness before implementation.

Inputs:

- `requirement_id`
- acceptance criteria
- target module
- project stack

Allowed tools:

- `project.inspect`
- `test.discover`
- `filesystem.patch`
- `git.diff`

Outputs:

- harness file path
- test cases generated
- fixtures needed
- unsupported criteria

Writes:

- `tests/harness/...`
- optional fixture files

Gates:

- harness must fail before implementation when feasible
- generated tests must be scoped to the requirement
- no production code changes in this skill

Success criteria:

- running the focused harness gives a meaningful failing signal or a documented skip reason

### `harness.review`

Purpose: verify that the generated harness actually represents the requirement.

Inputs:

- `requirement_id`
- harness diff
- acceptance criteria

Allowed tools:

- `git.diff`
- `test.pytest`
- `test.ruff`

Outputs:

- review decision: accept, revise, ask user
- missing coverage
- false-positive risks

Writes:

- `audit.db.evaluations`

Gates:

- reject harnesses that only assert implementation details
- reject tests that can pass without the requested behavior

Success criteria:

- evaluator can explain which criterion each test covers

### `implementation.plan`

Purpose: produce a small-patch implementation plan after the harness exists.

Inputs:

- `requirement_id`
- accepted harness
- code context

Allowed tools:

- `shell.rg_search`
- `retriever.symbol_search`
- `knowledge.search`

Outputs:

- patch objectives
- allowed files
- forbidden files
- required checks
- rollback plan

Writes:

- `tasks.db.patch_queue`

Gates:

- split large implementation into small patches
- require confirmation for schema, public API, or security changes

Success criteria:

- each patch objective can be implemented and tested independently

### `patch.apply`

Purpose: apply one scoped implementation patch.

Inputs:

- `patch_id`
- allowed files
- objective

Allowed tools:

- `filesystem.patch`
- `shell.rg_search`
- `git.diff`

Outputs:

- changed files
- diff summary
- touched criteria

Writes:

- production code files
- test files only if harness revision is explicitly required

Gates:

- stay inside allowed files
- stay inside patch size limits
- no dependency changes without confirmation

Success criteria:

- focused harness moves from failing to passing, or failure is explained

### `harness.run`

Purpose: run generated tests and required static checks.

Inputs:

- `requirement_id`
- `patch_id`
- test command IDs

Allowed tools:

- `test.pytest`
- `test.ruff`
- `test.mypy`
- `test.npm`

Outputs:

- command results
- failing cases
- coverage of acceptance criteria

Writes:

- `audit.db.tool_runs`
- `tasks.db.check_results`

Gates:

- tests must be focused first
- broad test suite runs only after focused harness passes

Success criteria:

- every required command has a recorded result

### `evaluator.score`

Purpose: score the patch against requirements, harness results, risk, and evidence.

Inputs:

- requirement record
- acceptance criteria
- harness results
- diff
- audit evidence

Allowed tools:

- `git.diff`
- `audit.read`
- `knowledge.search`

Outputs:

- correctness score
- completeness score
- evidence quality
- ambiguity score
- risk score
- final score
- recommended decision

Writes:

- `audit.db.evaluations`

Gates:

- no passing score without test or explicit manual evidence

Success criteria:

- decision is reproducible from stored evidence

### `decision.gate`

Purpose: decide whether to accept, retry, ask user, ask tech lead, or stop.

Inputs:

- evaluator result
- risk flags
- retry count
- confirmation policy

Allowed tools:

- `confirmation.create`
- `tasks.update`
- `memory.write`

Outputs:

- decision
- reason
- next action

Writes:

- `tasks.db.decisions`
- optional `memory.db` for confirmed rules

Gates:

- ask user if ambiguity is high
- ask tech lead if architecture, schema, security, or public API risk is high
- stop after retry budget is exhausted

Success criteria:

- unsafe or ambiguous changes do not proceed silently
