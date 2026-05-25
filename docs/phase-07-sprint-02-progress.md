# Phase 07 Sprint 02 Progress

Sprint focus:

- `F-SKILL-003`: skill script sandbox and side-effect policy

## Functional `F-SKILL-003`

Before gate summary:

Sprint 01 added package trust verification. Sprint 02 constrains scripts that
belong to a verified package: scripts must not run from untrusted or
quarantined packages, must use registered and declared tools, and must keep
side effects behind approval or trusted package policy.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli skills
```

After gate summary:

`SkillScriptRequest` and `evaluate_skill_script` define the sandbox policy.
Unverified packages deny script execution and quarantined packages stay
quarantined. Registered tools must also be declared by package policy. Write,
process, and network tools require explicit approval or trusted package policy.
Allowed script output remains data and routes to evidence rank when evidence
refs exist, otherwise to knowledge verification.

## Sprint Exit

- Scripts are disabled unless package trust is verified.
- Script tools must be both registered and declared.
- Side-effect tools require approval or trusted package policy.
- Script policy decisions emit audit events.
- Script output cannot bypass evidence or knowledge gates.
