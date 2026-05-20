# Requirement Sources

Requirement parsing must read the main Notion architecture page and the configured sub pages below.

## Sources

| Role | Title | URL |
| --- | --- | --- |
| Main | AI Infranstructure | https://www.notion.so/AI-Infranstructure-32db38678ea58058a66af365862c301e |
| Sub page | Thread Control, Queue, Outbox & Prompt Injection Security | https://www.notion.so/365b38678ea581f1876ae3459ec1f686 |
| Sub page | Personal Memory Evaluation Formula & Governance | https://www.notion.so/365b38678ea581c2bbcbf79d42a9c1f2 |
| Sub page | Triết lý Agent Memory: Hồi quy, Truy hồi, Evidence và Rating | https://www.notion.so/366b38678ea581629d45fb6a245eacd9 |

## Extraction Rule

- Fetch every configured source before requirement extraction.
- Preserve page title and URL on each extracted requirement.
- If a source cannot be fetched, mark the requirement parse as incomplete.
- Do not silently continue with only the main page.
- Child-page discovery should be repeated when the main page changes.

## Coverage Output

```yaml
source_coverage:
  expected_sources: 4
  fetched_sources: 4
  missing_sources: []
  extracted_requirements_by_source:
    AI Infranstructure: 0
    Thread Control, Queue, Outbox & Prompt Injection Security: 0
    Personal Memory Evaluation Formula & Governance: 0
    Triết lý Agent Memory: Hồi quy, Truy hồi, Evidence và Rating: 0
```

