# Phase 07 Entry Plan

## Entry State

Phase 6 closed the custom skill metadata, permission, and output handoff
boundary. Skills can now be loaded from `SKILL.md`, constrained by allowlisted
tools, routed through evidence and confirmation gates, and audited through
handoff metadata.

Phase 7 should treat skills as executable/distributable artifacts. The phase
must not reopen the Phase 6 authority boundary: skills remain workflows plus
metadata, not a permission system or policy override.

## Phase Theme

Phase 7 focus:

- skill execution safety
- skill package verification
- install/update auditability
- script sandbox policy
- distribution trust boundaries

## Candidate Functional Scope

### `F-SKILL-002`: Skill Package Trust

Build a local trust boundary for installable skills:

- package identity and stable skill id
- source URL or local source ref
- package checksum
- trusted/untrusted status
- signed or unsigned package metadata
- install/update audit record
- deny-by-default behavior for unknown package source

Focused gates to add or reuse:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli operational-safety
python -m ai_local.cli prompt-injection
python -m ai_local.cli noise
```

### `F-SKILL-003`: Skill Script Sandbox

Constrain scripts bundled with skills:

- scripts are disabled by default for untrusted skills
- script execution requires declared tool permission
- write/process/network side effects require explicit approval or a trusted
  package policy
- script output is data until routed through evidence rank or confirmation
- script execution emits audit records with command, cwd, timeout, and result

Focused gates to add or reuse:

```powershell
python -m ai_local.cli tool-combo
python -m ai_local.cli operational-safety
python -m ai_local.cli patch-pipeline
python -m ai_local.cli skills
```

### `F-SKILL-004`: Skill Install/Update Lifecycle

Add a lifecycle for local skill installation and updates:

- discover candidate
- inspect manifest/frontmatter
- verify checksum/source
- classify risk and trust
- install into a controlled skill root
- update only with audit trail
- rollback failed install/update
- refuse malformed or policy-shadowing skills

Focused gates to add or reuse:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli request-lifecycle
python -m ai_local.cli operational-safety
python -m ai_local.cli global-developer
python -m ai_local.cli developer-sprints
```

## Out Of Scope

Do not include these in Phase 7 without an explicit scope change:

- enterprise RBAC
- multi-user approval workflows
- public marketplace publishing
- remote code execution without sandboxing
- automatic trust of skills from the internet
- direct skill authority over memory policy, patch approval, or tool policy
- production deployment automation

## Entry Checklist

Before the first Phase 7 patch:

1. State whether the patch touches package trust, script execution, install
   lifecycle, audit records, checksum/signature verification, or sandbox policy.
2. Select focused gates from this plan and record expected risk.
3. Keep skill source refs, package refs, checksums, trust state, allowed tools,
   and audit refs explicit in the runtime contract.
4. Run focused gates before widening to full Phase 1-6 regression and
   promotion gates.

## Close Criteria

Phase 7 can close only when:

1. Installable skills fail closed when source, checksum, manifest, or trust
   policy is missing.
2. Skill scripts cannot run write/process/network side effects unless the
   package and tool policy allow it.
3. Install/update/run events are auditable.
4. Skill output still routes through Phase 6 handoff and Phase 5 evidence,
   knowledge, memory, and confirmation gates.
5. Full CLI gates, harness regression, pytest, ruff, mypy, and promotion gates
   pass together.
