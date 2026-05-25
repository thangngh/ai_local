# Phase 07 Sprint 01 Progress

Sprint focus:

- `F-SKILL-002`: skill package trust and source verification

## Functional `F-SKILL-002`

Before gate summary:

Phase 7 starts from a closed Phase 6 skill runtime. Skill output is already
permission-gated and routed through downstream evidence gates, but installable
skill packages still need a local trust boundary before Phase 7 can add script
or install/update behavior.

Gate commands:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli prompt-injection
.\.venv\Scripts\python -m ai_local.cli noise
```

After gate summary:

`SkillPackageManifest` and `verify_skill_package` define the package trust
boundary. Package verification fails closed when package id, skill id, source
ref, checksum, manifest identity, or trust state is missing. Unknown sources,
checksum mismatch, untrusted packages, and manifest identity mismatch are
denied; policy-shadowing package metadata is quarantined. Successful package
verification records an audit event.

## Sprint Exit

- Package identity and skill identity are explicit.
- Source refs, checksums, trust state, signed metadata, manifest identity, and
  risk level are visible in the trust contract.
- Missing or mismatched trust inputs fail closed.
- Package verification emits audit evidence for install lifecycle work in a
  later sprint.
