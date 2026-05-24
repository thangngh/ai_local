# Phase 06 Sprint 03 Progress

Sprint focus:

- `F-SKILL-001`: skill output handoff into evidence, knowledge, memory,
  decision, and patch gates

## Functional Scope

Sprint 01 covered skill metadata and registry loading. Sprint 02 hardened tool
permission decisions. Sprint 03 closes the remaining skill boundary: a skill
may produce useful workflow/search/analysis output, but that output must remain
data until the normal evidence and downstream gates accept it.

Before gate summary:

Skill requests were permission-gated, but output handoff was specialized around
web research. The remaining risk was that another skill output shape could be
treated as a fact, policy, memory, decision, or patch request without evidence
rank and confirmation.

Gate commands:

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
```

After gate summary:

`SkillOutputEnvelope` now represents generic skill output with output kind,
source refs, evidence refs, risk flags, and requested downstream gate. The
handoff router sends evidenced output to evidence rank, unevidenced output to
knowledge verification, privileged patch/policy/decision requests to
confirmation, prompt-injected output to quarantine, and deep policy-shadowing
output to stop. Web research output uses the same envelope path.

## Sprint Exit

- Skill output cannot become fact, memory, policy, decision, or patch authority
  by itself.
- `simple-workflow` output routes through evidence rank before use.
- Weak or unevidenced skill output verifies before knowledge use.
- Prompt injection and deep policy shadowing remain quarantined or stopped.
- Phase 6 is ready for close gates.
