# Phase 07 Sprint 03 Progress

## Scope

Implemented `F-SKILL-004`: skill install and update lifecycle policy.

The sprint adds a pre-install/pre-update gate for skill packages before any filesystem installer exists. The lifecycle policy keeps install/update behavior explicit and testable:

- package trust must already be verified
- install target must be a controlled skill root
- manifest and skill frontmatter must be inspected
- checksum, source, and risk classification must be complete
- updates require a previous package audit reference
- updates require rollback availability
- failed lifecycle attempts either roll back or stop
- policy-shadowing packages are quarantined

## Runtime

`SkillLifecycleRequest` and `evaluate_skill_lifecycle` define the lifecycle policy.

Allowed outcomes:

- `allow_install`
- `allow_update`
- `rollback`
- `deny`
- `quarantine`

All lifecycle evaluations emit audit events when an audit store is provided.

## Gate Summary

Focused gates for this sprint:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli request-lifecycle
python -m ai_local.cli operational-safety --max-level hard
python -m ai_local.cli global-developer
python -m ai_local.cli developer-sprints
```

Regression focus:

```powershell
python -m pytest tests/test_skill_runtime.py
python -m pytest tests/harness
python -m ruff check .
python -m mypy ai_local tests
```
