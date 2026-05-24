# Phase 06 Close Checklist

## Close Scope

Phase 6 can close when skill workflows stay bounded by permission and evidence:

- skill metadata parsing preserves id, name, description, risk level, trust,
  allowed tools, and workflow body
- registry loading fails closed for missing or malformed skill definitions
- skill tool requests are limited to both the skill allowlist and registered
  tool surface
- unknown skills and unlisted tools are denied
- untrusted skills cannot write memory policy or grant themselves permissions
- skill output is routed to evidence rank, knowledge, memory, confirmation, or
  quarantine before it can influence facts or side effects
- prompt-injected and deep policy-shadowing skill output is quarantined or
  stopped
- skill handoff preserves Phase 5 knowledge and memory gates
- tool-combo and patch pipeline gates still own side effects and patch writes

## Phase Gates

Run the Phase 6 focused gate surface:

```powershell
python -m ai_local.cli skills
python -m ai_local.cli tool-combo
python -m ai_local.cli prompt-injection
python -m ai_local.cli noise
```

Run the cross-phase gates that Phase 6 can affect:

```powershell
python -m ai_local.cli evidence-rank
python -m ai_local.cli knowledge
python -m ai_local.cli memory-governance
python -m ai_local.cli decision
python -m ai_local.cli patch-pipeline
python -m ai_local.cli operational-safety
python -m ai_local.cli global-developer
python -m ai_local.cli developer-sprints
```

## Regression Gates

Use the same close regression standard as earlier phases:

```powershell
python -m pytest tests\harness
python -m pytest
python -m ruff check ai_local tests
python -m mypy ai_local tests
python -m ai_local.cli promote
```

## Close Decision

Close Phase 6 only when:

1. `F-SKILL-001` focused gates pass with extreme skill laundering coverage.
2. Prompt injection and noise gates show retrieved skill content remains data,
   not instruction.
3. Evidence rank, knowledge, memory governance, and decision gates show no
   skill output can become fact, policy, memory, or side effect without the
   normal downstream gates.
4. Full harness, pytest, lint, type, and promotion regression pass.

## Next Phase Handoff

Any later phase should consume skill results as audited, ranked, and gated
workflow output. Skills must remain workflows plus metadata; they are not a
permission system, policy source, or authority override.
