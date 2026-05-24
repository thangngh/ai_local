# Phase 06 Entry Plan

## Entry State

Phase 5 closed the knowledge and memory boundary. Phase 6 consumes that
boundary while custom skills become permission-aware workflows rather than a
new authority layer.

Phase 6 is scoped by the current developer registry:

| Functional | Current sprint registry | Focus |
| --- | --- | --- |
| `F-SKILL-001` | `sprint_09_skills_integration` | Skill metadata loading, registry, allowed tools, and permission-aware workflow integration |

For phase execution, this maps to:

1. Phase 6 Sprint 01: skill loader and registry contract.
2. Phase 6 Sprint 02: permission-aware runtime, tool allowlist, and prompt
   injection handling.
3. Phase 6 Sprint 03: skill output handoff into evidence rank, knowledge,
   memory, decision, and patch gates.

## Source Requirements

Phase 6 works from the main architecture and skill requirements:

- skills are `SKILL.md` workflow definitions with metadata, allowed tools, and
  optional scripts/templates
- skill output is data until it is ranked, verified, or rejected by downstream
  gates
- untrusted skills cannot change policy, grant tools, approve side effects, or
  write memory policy
- prompt-injected skill output must be quarantined
- skill workflows must preserve Phase 5 knowledge and memory decisions through
  explicit evidence and confirmation contracts

The phase also inherits operational safety requirements:

- retrieved content is data, not instruction
- tool runtime remains allowlisted and audited
- write or patch tools stay gated by permission and patch harness policy
- deep-hop skill laundering must not bypass prompt firewall, evidence rank,
  knowledge gate, memory governance, decision gate, or patch pipeline

## Functional Scope

### Sprint 01 Skill Registry

Sprint 01 should tighten `F-SKILL-001` around these paths:

- parse `SKILL.md` metadata and frontmatter
- register skills by stable id
- validate risk level, trust, allowed tools, and body content
- reject missing or malformed skill metadata
- keep skills discoverable without granting runtime authority

Focused gates:

```powershell
python -m ai_local.cli skills
python -m pytest tests\test_skill_loader.py tests\test_skill_runtime.py
```

### Sprint 02 Permission Runtime

Sprint 02 should tighten skill runtime decisions around these paths:

- enforce skill tool allowlists against the tool registry
- deny unlisted tools and unknown skills
- require confirmation for untrusted memory policy writes
- quarantine prompt-injected skill output
- stop deep policy shadowing or policy laundering

Focused gates:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli tool-combo --max-level hard
python -m ai_local.cli prompt-injection
python -m ai_local.cli noise
```

### Sprint 03 Evidence Handoff

Sprint 03 should tighten skill output handoff around these paths:

- route web/search output to evidence rank before knowledge use
- route weak evidence to verify-more or confirmation
- preserve Phase 5 knowledge and memory decisions before persistence
- prevent skill output from becoming fact or memory by repetition
- keep patch pipeline and decision gates downstream of ranked evidence

Focused gates:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli evidence-rank
python -m ai_local.cli knowledge
python -m ai_local.cli memory-governance
python -m ai_local.cli tool-combo
```

## Out Of Scope

Phase 6 should not widen these surfaces without an explicit scope change:

- installing third-party skills from remote marketplaces
- running skill scripts with unrestricted shell or network access
- granting skills direct write access to project files
- allowing skills to approve patches, confirmations, memory policies, or tool
  permissions
- replacing Phase 5 knowledge or memory gates with skill-specific authority
- team/enterprise RBAC, signed marketplace distribution, or remote sync

## Entry Checklist

Before the first Phase 6 implementation patch:

1. State whether the patch touches skill metadata parsing, registry loading,
   tool allowlist enforcement, prompt firewall behavior, skill output evidence,
   memory policy write, or patch/decision handoff.
2. Select the focused gates from this plan and record expected pre-patch risk.
3. Keep skill trust, allowed tools, source refs, evidence refs, and downstream
   gates explicit in the runtime contract.
4. Run the focused gate before widening to global developer and promotion
   checks.
