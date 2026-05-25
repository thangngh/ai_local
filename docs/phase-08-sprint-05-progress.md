# Phase 08 Sprint 05 Progress

## Scope

Implemented `F-SKILLRT-005`: agent-loop skill runtime path.

This sprint connects the verified skill script runtime to the agent loop. Skill
execution now flows through runtime policy, subprocess runner, evidence handoff,
observation evaluation, and decision routing.

## Runtime

`AgentLoop.execute_skill_runtime` now:

- accepts a `SkillScriptRunRequest`
- invokes configured skill runtime
- converts script output into evidence handoff
- builds evaluation evidence refs and skill-runtime refs
- routes successful completion to `DONE`
- routes failed scripts to retry or re-plan by retry budget
- routes approval-required scripts to `ASK_USER`
- routes stopped or rejected skill evidence to rollback
- updates run state when `task_id` is provided

## Gate Summary

Focused gates for this sprint:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level hard
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
.\.venv\Scripts\python -m ai_local.cli evidence-rank
.\.venv\Scripts\python -m ai_local.cli global-developer
.\.venv\Scripts\python -m ai_local.cli developer-sprints
```

Close gate:

```powershell
.\.venv\Scripts\python -m pytest tests\harness
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m ai_local.cli promote
```
