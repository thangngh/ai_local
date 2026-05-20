# Development

## Virtual Environment

Create the environment:

```powershell
python -m venv .venv
```

Install the project:

```powershell
.\.venv\Scripts\python -m pip install -e .[dev]
```

## Patch Gate Flow

Every implementation patch starts with small gates. Only promote to the next level when the current level passes.

1. Easy: focused harness tests for the requirement.
2. Medium: full pytest suite.
3. Hard: ruff and mypy.
4. Extreme: expensive or cross-stack checks such as `npm test`.

Commands:

```powershell
.\.venv\Scripts\python -m pytest tests\harness
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check
.\.venv\Scripts\python -m mypy ai_local tests
```

The CLI gate runner can execute configured command IDs from `configs/tools.yaml`:

```powershell
.\.venv\Scripts\python -m ai_local.cli gate test.pytest test.ruff test.mypy
```

The promotion runner executes `configs/gates.yaml` in order and stops on the first failed required level:

```powershell
.\.venv\Scripts\python -m ai_local.cli promote
```

To stop at a specific level:

```powershell
.\.venv\Scripts\python -m ai_local.cli promote --max-level hard
```

## Current Package Layout

```text
ai_local/
  api/
  agent/
  audit/
  config/
  evaluator/
  harness/
  indexer/
  knowledge/
  memory/
  outbox/
  planner/
  queue/
  retrieval/
  tools/
```
