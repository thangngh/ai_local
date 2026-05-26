# Phase 10 Sprint 03 Progress

Sprint 03 hardens the production tool execution path by moving skill subprocess
execution behind a sandbox adapter boundary.

## Functional Scope

- `ai_local.tools.sandbox` defines the sandbox policy, request/result contract,
  adapter protocol, and default local subprocess adapter.
- The default adapter fails closed for:
  - cwd escaping the workspace root
  - empty commands
  - shell execution flags
  - timeout values above the policy cap
  - executables missing from the allowlist
  - shell-like metacharacters in argv
  - Docker or bubblewrap backends before an actual backend is configured
- `SkillScriptRunner` now routes allowlisted skill subprocesses through the
  sandbox adapter and preserves existing evidence/patch/timeout routing.
- `tool-sandbox-check` gives the TUI/control-plane layer a small CLI probe for
  validating a command against sandbox policy.

## Gate Harness

Focused tests:

```powershell
.\.venv\Scripts\python -m pytest tests/test_tool_sandbox.py tests/test_skill_runner.py tests/test_tool_executor.py tests/test_skill_runtime.py
```

Combined safety gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
.\.venv\Scripts\python -m ai_local.cli prompt-injection --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
```

Quality gates:

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m pytest
```

## Run Summary

- Focused tests: `42 passed`
- `tool-combo --max-level hard`: passed through hard, max hop depth 25
- `prompt-injection --max-level hard`: passed through hard, max hop depth 25
- `operational-safety --max-level hard`: passed through hard, max hop depth 30
- `ruff check .`: passed
- `mypy ai_local tests`: passed, 185 source files
- Full pytest: `288 passed, 1 skipped`

Pytest still reports a local `.pytest_cache` permission warning; it does not
affect runtime behavior.
