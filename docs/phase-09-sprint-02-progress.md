# Phase 09 Sprint 02 Progress

Implemented Phase 9 Sprint 02: persisted end-to-end evidence and audit chain.

## Functional Scope

Sprint 01 produced a deterministic JSON integration report. Sprint 02 persists
that report into SQLite so output readiness, evidence refs, route reasons, and
runtime audit events can be replayed after the CLI exits.

Implemented:

- `PipelineAuditChainStore`
- SQLite tables under `audit.db`:
  - `phase9_pipeline_runs`
  - `phase9_pipeline_stages`
  - `phase9_pipeline_evidence_refs`
  - `phase9_pipeline_risk_flags`
  - `phase9_pipeline_reasons`
  - `phase9_pipeline_audit_events`
- `phase9-integration-report --audit-db <path>`
- `phase9-audit-chains --audit-db <path>`

## CLI Examples

Persist a ready report:

```powershell
.\.venv\Scripts\python -m ai_local.cli phase9-integration-report `
  --scenario ready `
  --workspace-root . `
  --audit-db audit.db
```

List persisted chains:

```powershell
.\.venv\Scripts\python -m ai_local.cli phase9-audit-chains `
  --audit-db audit.db
```

## Gate Harness

Focused gate:

```powershell
.\.venv\Scripts\python -m pytest tests/test_phase9_audit_chain.py tests/test_phase9_report.py
```

Expected behavior:

- the report includes a `chain_id` when `--audit-db` is supplied
- evidence refs and audit event counts are persisted
- no-path rollback chains remain queryable
- CLI listing shows scenario, status, final state, evidence count, and audit
  event count

## Assessment

This sprint closes the auditability gap identified in the Phase 9 improvement
plan. The persisted chain is intentionally narrow and report-oriented. It does
not replace the domain stores, but it gives each integration report a durable
proof trail that can be used by replay fixtures and later stress gates.
