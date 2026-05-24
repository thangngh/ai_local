# Phase 06 Close Report

## Close Scope

Phase 6 closes the custom skill workflow boundary:

- `SKILL.md` metadata loads through the skill registry
- skills can use skills.sh-compatible frontmatter such as `allowed-tools`
- custom `simple-workflow` is present as a lightweight local workflow skill
- skill tool requests are limited by skill allowlist and runtime tool registry
- unknown skills, unknown tools, unlisted tools, unregistered tools, direct
  write/process side effects, and approval-gated tools fail closed for
  untrusted skills
- prompt-injected skill output is quarantined
- deep policy-shadowing skill output stops
- skill output remains data until evidence-ranked, verified, confirmed,
  quarantined, or stopped
- privileged patch, decision, and memory-policy handoff attempts route to
  confirmation
- handoff metadata records audit requirement, source refs, evidence refs, and
  privileged request state

## Closure Gates

Phase close gates:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli tool-combo
python -m ai_local.cli prompt-injection
python -m ai_local.cli noise
python -m ai_local.cli evidence-rank
python -m ai_local.cli knowledge
python -m ai_local.cli memory-governance
python -m ai_local.cli decision
python -m ai_local.cli patch-pipeline
python -m ai_local.cli operational-safety
python -m ai_local.cli global-developer
python -m ai_local.cli developer-sprints
```

Full cross-phase gate surface:

```powershell
python -m ai_local.cli request-lifecycle
python -m ai_local.cli thread-control
python -m ai_local.cli agent-loop
python -m ai_local.cli retrieval
python -m ai_local.cli flow-memory-rating
python -m ai_local.cli memory-sql
python -m ai_local.cli big-harness
python -m ai_local.cli small-patch
python -m ai_local.cli patch-levels
python -m ai_local.cli composite
python -m ai_local.cli conflict-paths
python -m ai_local.cli evaluation
python -m ai_local.cli confirmation
python -m ai_local.cli multi-conflict
python -m ai_local.cli memory-layers
python -m ai_local.cli memory-regression
```

Regression gates:

```powershell
python -m pytest tests\harness
python -m pytest
python -m ruff check ai_local tests
python -m mypy ai_local tests
python -m ai_local.cli promote
```

## Exit Decision

Phase 6 can close when the focused skill gates, cross-phase evidence/knowledge/
memory/decision/patch gates, and full regression gates pass together.

Later work should be treated as a new phase or explicit scope change if it
involves remote marketplace install, signed skill packages, unrestricted skill
scripts, stronger container sandboxing, RBAC, or team distribution.
