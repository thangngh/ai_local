# Global Developer Harness

The global developer harness validates the phase planning layer above focused
gate harnesses. It loads the main Notion MVP phase order, functional items,
non-functional items, and gate inventory from
`configs/global_developer_harness.yaml`.

The rule is direct: every functional requirement must have gate harness coverage
before phase developer work claims it is ready.

Run it with:

```powershell
.\.venv\Scripts\python -m ai_local.cli global-developer
```
