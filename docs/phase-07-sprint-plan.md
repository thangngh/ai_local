# Phase 07 Sprint Plan

## Phase Scope

Phase 7 turns the Phase 6 skill workflow boundary into a distribution and
execution safety boundary. Skills remain data-driven workflows until package
trust, script policy, install/update lifecycle, and downstream evidence gates
accept them.

## Sprint Cuts

| Sprint | Functional | Objective |
| --- | --- | --- |
| Phase 7 Sprint 01 | `F-SKILL-002` | Establish package identity, source verification, checksum, trust state, and install audit boundaries. |
| Phase 7 Sprint 02 | `F-SKILL-003` | Constrain bundled scripts, side effects, approval requirements, script output handoff, and execution audit fields. |
| Phase 7 Sprint 03 | `F-SKILL-004` | Add install/update lifecycle with controlled skill root, rollback, malformed-skill refusal, and audit evidence. |

## Sprint 01 Package Trust

Focused behavior:

- stable package and skill identity
- source URL or local source ref
- checksum verification
- trusted/untrusted package state
- manifest identity validation
- install audit event shape
- deny by default when source, checksum, or trust policy is missing

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli prompt-injection
.\.venv\Scripts\python -m ai_local.cli noise
```

## Sprint 02 Script Sandbox

Focused behavior:

- scripts disabled by default for untrusted packages
- script execution requires declared tool permission
- write/process/network side effects require explicit approval or trusted
  package policy
- script output remains data until evidence rank or confirmation
- script execution audit records command, cwd, timeout, result, and package ref

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli skills
```

## Sprint 03 Install/Update Lifecycle

Focused behavior:

- discover candidate package
- inspect manifest and `SKILL.md` frontmatter
- verify checksum and source
- classify risk and trust
- install into a controlled skill root
- update with audit trail
- rollback failed install/update
- refuse malformed, prompt-injected, or policy-shadowing packages

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli global-developer
.\.venv\Scripts\python -m ai_local.cli developer-sprints
```

## Close Gate

Phase 7 can close when all three functionals pass together, then the full
cross-phase regression passes:

```powershell
.\.venv\Scripts\python -m pytest tests\harness
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\ruff check ai_local tests
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m ai_local.cli promote
```
