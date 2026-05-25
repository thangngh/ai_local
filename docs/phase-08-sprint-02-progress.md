# Phase 08 Sprint 02 Progress

## Scope

Implemented `F-SKILLRT-002`: installed skill registry and stale cleanup.

This sprint adds a local SQLite-backed registry for installed skills. It records
the runtime state that future script execution and agent-loop integration need
without changing the agent runtime path yet.

## Runtime

`InstalledSkillStore` persists:

- package id
- skill id
- source ref
- checksum
- controlled root
- `SKILL.md` path
- trust state
- risk level
- lifecycle audit ref
- modified timestamp

Registry maintenance helpers:

- `refresh_installed_skill_registry`
- `cleanup_stale_installed_skills`
- `rebuild_installed_skill_registry`

CLI maintenance hooks:

```powershell
.\.venv\Scripts\python -m ai_local.cli skill-registry-refresh
.\.venv\Scripts\python -m ai_local.cli skill-registry-cleanup
.\.venv\Scripts\python -m ai_local.cli skill-registry-rebuild
.\.venv\Scripts\python -m ai_local.cli skill-registry-stats
```

## Gate Summary

Focused gates for this sprint:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli memory-sql
.\.venv\Scripts\python -m ai_local.cli developer-sprints
```

Regression focus:

```powershell
.\.venv\Scripts\python -m pytest tests\test_skill_store.py tests\test_skill_runtime.py
.\.venv\Scripts\python -m ruff check ai_local\skills ai_local\cli.py tests\test_skill_store.py
.\.venv\Scripts\python -m mypy ai_local\skills ai_local\cli.py tests\test_skill_store.py
```
