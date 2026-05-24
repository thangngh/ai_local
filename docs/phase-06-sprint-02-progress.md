# Phase 06 Sprint 02 Progress

Sprint focus:

- `F-SKILL-001`: permission-aware skill runtime hardening

## Functional Scope

Sprint 01 proved skill metadata and registry loading with the `simple-workflow`
custom skill. Sprint 02 tightens runtime permission decisions so skill metadata
cannot accidentally grant write, process, approval-gated, unregistered, or
policy-changing capability.

Before gate summary:

Skill requests already route through the skill registry and tool allowlist.
The remaining runtime risk is a trust or registry mismatch: a skill may name a
tool that is allowlisted in skill metadata but not registered in the runtime, or
an untrusted skill may be misconfigured with direct write/process tool access.

Gate commands:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli tool-combo --max-level hard
python -m ai_local.cli prompt-injection
python -m ai_local.cli noise
```

After gate summary:

`SkillDecisionResult` now exposes the skill trust/risk profile and requested
tool permission facts: whether the tool is registered, allowlisted, audited,
approval-gated, and what side-effect level it carries. Runtime decisions deny
unknown skills, unregistered tools, non-allowlisted tools, approval-gated tools
from untrusted skills, and direct write/process tools from untrusted skills even
if metadata is misconfigured. Network/read tools can still run when they are
registered, allowlisted, and governed by downstream evidence/prompt gates.

## Sprint Exit

- Skill runtime fails closed for unknown skills and unregistered tools.
- Untrusted skills cannot directly invoke write or process side-effect tools.
- Prompt-injected and deep policy-shadowing skill paths remain quarantined or
  stopped by existing gates.
- Permission decisions preserve enough metadata for audit and downstream gates.
