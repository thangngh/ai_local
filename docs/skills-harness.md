# Skills Harness

This harness validates custom skills and module combinations.

Custom skill:

- `skills/web-research/SKILL.md`

Combo flow:

```text
requirement -> memory -> skill -> web_search -> retrieval -> evidence_rank -> knowledge_gate -> decision -> patch_pipeline
```

Rules:

- skill may only use allowlisted tools
- untrusted skill cannot change policy
- skill output is data until evidence ranked
- prompt-injected skill output is quarantined
- skill memory policy write requires confirmation

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli skills
```

