# Requirements to Harness Pipeline

This project uses a requirement-driven development flow. The agent must create the test harness before production implementation.

Primary requirement sources:

- https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e
- https://www.notion.so/365b38678ea581f1876ae3459ec1f686
- https://www.notion.so/365b38678ea581c2bbcbf79d42a9c1f2
- https://www.notion.so/366b38678ea581629d45fb6a245eacd9

## Pipeline

1. Fetch the primary Notion requirement source and all listed sub pages.
2. Parse requirements into structured records.
3. Normalize requirements into acceptance criteria.
4. Generate focused harness tests.
5. Review the harness against the criteria.
6. Run the harness and record the pre-implementation signal.
7. Plan a small implementation patch.
8. Apply the patch.
9. Run focused harness tests.
10. Run broader checks when focused tests pass.
11. Score the result.
12. Accept, retry, ask for confirmation, or stop.

## Requirement Record

```yaml
id: REQ-001
source_ref: https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e
goal: Short behavior statement
actors:
  - user
constraints:
  - local-first
  - SQLite-backed
in_scope:
  - behavior to implement
out_of_scope:
  - explicitly excluded behavior
ambiguities:
  - question that needs confirmation
risk_flags:
  - schema_change
evidence:
  - source_ref: https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e
    summary: Source statement
```

## Acceptance Criteria

```yaml
criteria:
  - id: AC-001
    requirement_id: REQ-001
    statement: Worker leases only pending jobs.
    observable_by: pytest
    expected_signal: a second worker cannot lease the same job.
    negative_cases:
      - cancelled jobs are not leased
```

## Harness Manifest

```yaml
harness:
  id: HAR-001
  requirement_id: REQ-001
  test_files:
    - tests/harness/test_queue_leasing.py
  criteria_map:
    AC-001:
      - tests/harness/test_queue_leasing.py::test_worker_cannot_double_lease_job
  pre_implementation_expectation: fail
  required_commands:
    - pytest tests/harness/test_queue_leasing.py
```

## Gate Rules

- No implementation patch before `harness.review` accepts the harness.
- Requirement parsing must include the main Notion page and all configured sub pages.
- If a harness cannot be automated, create a manual gate with evidence requirements.
- Generated tests must map to acceptance criteria.
- A test that can pass without the requested behavior is invalid.
- Production file writes are blocked until the harness is accepted.
- High-risk changes require confirmation before implementation.
