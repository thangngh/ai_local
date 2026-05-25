# Phase 08 Sprint 01 Progress

## Scope

Implemented `F-SKILLRT-001`: controlled skill installer adapter.

The sprint connects the Phase 7 lifecycle decision to a bounded filesystem
adapter without introducing broader registry or agent-loop behavior yet.

## Runtime

`install_skill_package` applies a skill package only when lifecycle policy has
already returned `allow_install` or `allow_update`.

The adapter now enforces:

- source package directory must exist
- package must include `SKILL.md`
- lifecycle controlled root must match installer controlled root
- target directory stays inside the controlled skill root
- staging and rollback directories stay inside the staging root
- plain install refuses to overwrite an existing package
- update requires an existing target
- update preserves a rollback artifact
- failed update restores the previous package when rollback exists
- installer result emits audit events when an audit store is provided

## Gate Summary

Focused gates for this sprint:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli global-developer
```

Regression focus:

```powershell
.\.venv\Scripts\python -m pytest tests\test_skill_runtime.py
.\.venv\Scripts\python -m ruff check ai_local\skills tests\test_skill_runtime.py
.\.venv\Scripts\python -m mypy ai_local\skills tests\test_skill_runtime.py
```
