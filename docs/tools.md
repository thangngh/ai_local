# Tools

Tools are concrete callable capabilities. Skills may only call tools listed in the registry.

## Tool Contract

Each tool definition must include:

- `name`
- `description`
- `input_schema`
- `output_schema`
- `timeout_seconds`
- `side_effect_level`: none, read, write, process, network
- `allowed_roots`
- `audit_required`
- `approval_required`
- `risk_level`

## Requirement Tools

### `notion.fetch`

Purpose: fetch Notion requirement documents.

Default sources:

- https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e
- https://www.notion.so/365b38678ea581f1876ae3459ec1f686
- https://www.notion.so/365b38678ea581c2bbcbf79d42a9c1f2
- https://www.notion.so/366b38678ea581629d45fb6a245eacd9

Inputs:

- `url`
- optional `include_discussions`

Outputs:

- title
- source URL
- page content
- child page links

Policy:

- read-only
- source content must be stored as evidence reference, not treated as automatically complete

### `requirements.extract`

Purpose: extract structured requirements from source text.

Inputs:

- `source_text`
- `source_ref`

Outputs:

- requirement records
- source coverage report
- constraints
- ambiguities
- risk flags
- evidence refs

Policy:

- read-only
- does not create implementation tasks directly
- must preserve source page title and URL for every extracted requirement

### `requirements.read`

Purpose: load parsed requirement records from `tasks.db`.

### `acceptance_criteria.write`

Purpose: persist observable acceptance criteria.

Policy:

- write to `tasks.db`
- every criterion requires `requirement_id` and source evidence

## Harness Tools

### `test.discover`

Purpose: detect test framework, test paths, naming conventions, and existing fixtures.

Inputs:

- `root_path`

Outputs:

- framework
- test command candidates
- fixture patterns
- existing harness paths

Policy:

- read-only
- uses `rg`, file reads, and config inspection

### `harness.create_pytest`

Purpose: create a pytest harness from acceptance criteria.

Inputs:

- `requirement_id`
- `criteria`
- `target_module`
- `test_path`

Outputs:

- created test file
- test case IDs
- unsupported criteria

Policy:

- write only under `tests/`
- no production code changes

### `harness.map_criteria`

Purpose: map tests back to acceptance criteria.

Inputs:

- `test_file`
- `criteria`

Outputs:

- coverage map
- unmapped tests
- uncovered criteria

Policy:

- read-only

### `harness.run_focused`

Purpose: run the smallest generated or affected test set.

Inputs:

- `command_id`
- `test_path`
- optional `test_name`

Outputs:

- exit code
- passed count
- failed count
- failure summary

Policy:

- process execution
- timeout required
- audit required

## File and Search Tools

### `shell.rg_files`

Command: `rg --files`

Purpose: list files.

Policy:

- read-only
- root must be inside workspace

### `shell.rg_search`

Command: `rg <pattern>`

Purpose: search project text.

Policy:

- read-only
- pass arguments as argv, never interpolate shell strings

### `filesystem.patch`

Purpose: apply a structured patch.

Inputs:

- `target_files`
- `patch`
- `reason`

Outputs:

- changed files
- diff summary

Policy:

- write-scoped by harness allowed files
- audit required
- reject writes outside workspace

## Git Tools

### `git.status`

Command: `git status --short`

Policy:

- read-only

### `git.diff`

Command: `git diff -- <paths>`

Policy:

- read-only
- path constrained

## Test and Quality Tools

### `test.pytest`

Command: `pytest`

Policy:

- timeout required
- focused command before broad command
- audit required

### `test.ruff`

Command: `ruff check`

Policy:

- read-only unless separate `ruff_fix` tool is approved

### `test.mypy`

Command: `mypy`

Policy:

- read-only
- timeout required

### `test.npm`

Command: `npm test`

Policy:

- only enabled when `package.json` exists

## Evaluation and Gate Tools

### `audit.write`

Purpose: persist tool calls, decisions, and gate outcomes.

### `audit.read`

Purpose: load evidence for scoring.

### `evaluator.score_patch`

Purpose: score a patch against requirement, criteria, tests, and risk.

### `confirmation.create`

Purpose: create a structured confirmation request when ambiguity or risk blocks progress.

### `tasks.update`

Purpose: update task, patch, and decision state.

## Initial Allowlist

Read-only:

- `notion.fetch`
- `requirements.extract`
- `requirements.read`
- `test.discover`
- `harness.map_criteria`
- `shell.rg_files`
- `shell.rg_search`
- `git.status`
- `git.diff`
- `audit.read`

Write-scoped:

- `acceptance_criteria.write`
- `harness.create_pytest`
- `filesystem.patch`
- `audit.write`
- `tasks.update`

Process:

- `harness.run_focused`
- `test.pytest`
- `test.ruff`
- `test.mypy`
- `test.npm`

Approval required:

- production code writes before harness acceptance
- dependency changes
- schema migrations
- public API changes
- security-sensitive changes
- destructive shell or git commands
