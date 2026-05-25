# Phase 08 Sprint 03 Progress

## Scope

Implemented `F-SKILLRT-003`: skill script runner integration.

This sprint connects trusted skill script policy to a subprocess runtime while
keeping execution behind package trust, declared tool permission, approval,
bounded cwd, timeout, and evidence handoff.

## Runtime

`SkillScriptRunner` now:

- evaluates `SkillScriptRequest` with the existing sandbox policy before any subprocess starts
- runs only registered tools with a configured `command`
- builds command argv from the tool allowlist command plus script argv
- uses `subprocess.run` without shell execution
- bounds `cwd` to the configured workspace root
- caps runtime timeout by the tool definition timeout
- routes side-effect tools through approval before execution
- routes success to `evidence_rank`
- routes failed or timed-out scripts to `patch_pipeline`
- audits `skill.script.run` when an audit store is provided

## Gate Summary

Focused gates for this sprint:

```powershell
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli confirmation --max-level hard
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
```

Regression focus:

```powershell
.\.venv\Scripts\python -m pytest tests\test_skill_runner.py tests\test_skill_runtime.py
.\.venv\Scripts\python -m ruff check ai_local\skills tests\test_skill_runner.py
.\.venv\Scripts\python -m mypy ai_local\skills tests\test_skill_runner.py
```
