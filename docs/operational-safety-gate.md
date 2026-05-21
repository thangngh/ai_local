# Operational Safety Gate

This gate maps the Notion subpage for thread control, queue, outbox, worker,
prompt firewall, and local security into patch harness cases.

It checks that queue computation stays separate from outbox side effects, worker
crashes can be reclaimed, project write locks block conflicting write runs,
approval gates hold risky events, duplicate dispatch remains idempotent, and
high-risk retrieved content is quarantined before it reaches the decision path.

Run it with:

```powershell
.\.venv\Scripts\python -m ai_local.cli operational-safety
```
