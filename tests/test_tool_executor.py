from pathlib import Path

from ai_local.audit.store import InMemoryAuditStore
from ai_local.tools.executor import ToolExecutor
from ai_local.tools.registry import ToolRegistry
from ai_local.tools.schemas import ToolCall


ROOT = Path(__file__).resolve().parents[1]


def test_tool_executor_runs_registered_handler_and_audits() -> None:
    audit = InMemoryAuditStore()
    executor = ToolExecutor(
        ToolRegistry.from_yaml(ROOT / "configs" / "tools.yaml"),
        handlers={"web_search": lambda args: {"provider": args["provider"], "results": []}},
        audit_store=audit,
    )

    result = executor.execute(ToolCall(name="web_search", args={"provider": "duckduckgo"}))

    assert result.status == "succeeded"
    assert result.output == {"provider": "duckduckgo", "results": []}
    assert result.audited
    assert audit.list_events()[0].action == "tool.execute"


def test_tool_executor_denies_unknown_provider_and_secret_args() -> None:
    executor = ToolExecutor(ToolRegistry.from_yaml(ROOT / "configs" / "tools.yaml"))

    bad_provider = executor.execute(ToolCall(name="web_search", args={"provider": "other"}))
    secret_path = executor.execute(ToolCall(name="shell.rg_search", args={"path": ".env"}))
    unknown = executor.execute(ToolCall(name="shell.unknown"))

    assert bad_provider.status == "denied"
    assert bad_provider.error == "web search provider denied"
    assert secret_path.error == "secret path denied"
    assert unknown.error == "unknown tool"
