# Sprint 08 Progress

Sprint focus:

- `F-SKILL-001`: skill metadata loading and permission-aware workflow integration

## Functional `F-SKILL-001`

Before gate summary:

Sprint 08 turns the custom `web-research` skill metadata into runtime
permission decisions. Skill tool requests must preserve the skill allowlist,
registry membership, trust state, and memory policy boundary before any workflow
output is allowed into retrieval, evidence rank, or knowledge decisions.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
```

After gate summary:

Skill and tool-combo focused gates passed. Runtime skill registry loading now
uses markdown skill metadata, tool requests stay allowlisted and tool-registry
checked, untrusted policy-memory writes route to confirmation, suspicious output
routes to rank or quarantine paths, and deep policy shadowing stops.

## Sprint 08 Exit

Sprint 08 skill runtime baseline is present:

- Registered markdown skills load through a runtime registry keyed by skill id.
- Skill permission decisions cover allow, deny, verify-rank, verify-more,
  ask-user, quarantine, and stop paths.
- Skill workflow output remains an envelope with source URLs, evidence summary,
  risk flags, and an evidence-rank next gate.
- The untrusted `web-research` skill cannot grant patch tools or write policy
  memory without confirmation.

The current developer sprint plan is implemented through Sprint 08.
