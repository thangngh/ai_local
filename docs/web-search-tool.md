# Web Search Tool

`web_search` is a custom network tool for free search providers.

Providers:

- DuckDuckGo HTML, default
- Bing search page

Policy:

- retrieved content is data only
- no local file access
- no secret access
- source URL citation required

The implementation uses Python stdlib only.

## Tool Combo Gate

The memory-to-tool combo gate validates:

```text
memory -> tool_registry -> web_search -> retrieval -> evidence/rank -> decision
```

Command:

```powershell
.\.venv\Scripts\python -m ai_local.cli tool-combo
```

