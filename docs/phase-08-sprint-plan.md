# Phase 08 Sprint Plan

## Phase Scope

Phase 8 turns the Phase 7 skill distribution policy boundary into runtime
integration. The work keeps skill packages local-first, auditable, reversible,
and evidence-gated while connecting installer, registry, script runner, and
agent-loop paths.

## Sprint Cuts

| Sprint | Functional | Objective |
| --- | --- | --- |
| Phase 8 Sprint 01 | `F-SKILLRT-001` | Implement a controlled installer adapter with staging, atomic install, malformed package refusal, and rollback. |
| Phase 8 Sprint 02 | `F-SKILLRT-002` | Add installed skill state, stale package cleanup, and index refresh commands. |
| Phase 8 Sprint 03 | `F-SKILLRT-003` | Connect trusted skill scripts to subprocess runner policy, approval flow, timeout, and allowlist. |
| Phase 8 Sprint 04 | `F-SKILLRT-004` | Bind install, update, and script outputs to audit events and evidence rank handoff. |
| Phase 8 Sprint 05 | `F-SKILLRT-005` | Integrate the skill runtime path into the agent loop and close the phase with cross-module gates. |

## Sprint 01 Controlled Installer

Focused behavior:

- stage candidate package under a controlled staging root
- validate package trust and lifecycle result before writes
- install only inside the controlled skill root
- perform atomic install or explicit rollback
- reject malformed or policy-shadowing packages
- emit install audit evidence

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
.\.venv\Scripts\python -m ai_local.cli global-developer
```

## Sprint 02 Installed Registry

Focused behavior:

- persist installed package id, skill id, source ref, checksum, version, and root
- refresh installed skill index from disk
- clean stale rows when package files disappear
- expose maintenance command hooks
- preserve lifecycle audit references

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli memory-sql
.\.venv\Scripts\python -m ai_local.cli developer-sprints
```

## Sprint 03 Script Runner

Focused behavior:

- run scripts only for verified trusted packages
- require declared tool permission
- enforce subprocess command, cwd, timeout, and allowlist
- route write/process/network effects through approval
- keep script output behind evidence rank or knowledge gate

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli confirmation --max-level hard
.\.venv\Scripts\python -m ai_local.cli patch-pipeline
```

## Sprint 04 Audit And Evidence

Focused behavior:

- attach audit event ids to install, update, rollback, and script run results
- convert script output into evidence envelopes
- rank output before use in knowledge, memory, patch, or decision paths
- preserve conflict and unsafe-output routing

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli evidence-rank
.\.venv\Scripts\python -m ai_local.cli request-lifecycle
.\.venv\Scripts\python -m ai_local.cli operational-safety --max-level hard
.\.venv\Scripts\python -m ai_local.cli conflict-paths --max-level hard
```

## Sprint 05 Agent Loop Close

Focused behavior:

- let agent loop select a verified installed skill
- execute allowed skill runtime path
- feed output through evidence and decision gates
- retry, ask, stop, or rollback on failed runtime observations
- close Phase 8 with cross-module gates

Focused gates:

```powershell
.\.venv\Scripts\python -m ai_local.cli agent-loop --max-level hard
.\.venv\Scripts\python -m ai_local.cli skills
.\.venv\Scripts\python -m ai_local.cli tool-combo --max-level hard
.\.venv\Scripts\python -m ai_local.cli evidence-rank
.\.venv\Scripts\python -m ai_local.cli global-developer
.\.venv\Scripts\python -m ai_local.cli developer-sprints
```

## Close Gate

Phase 8 can close when all five functionals pass together, then full regression
and promotion pass:

```powershell
.\.venv\Scripts\python -m pytest tests\harness
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m mypy ai_local tests
.\.venv\Scripts\python -m ai_local.cli promote
```
