from collections.abc import Callable

from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.tools.registry import ToolRegistry
from ai_local.tools.schemas import ToolCall, ToolDefinition, ToolResult

ToolHandler = Callable[[dict[str, object]], dict[str, object]]


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        handlers: dict[str, ToolHandler] | None = None,
        audit_store: InMemoryAuditStore | None = None,
    ) -> None:
        self._registry = registry
        self._handlers = handlers or {}
        self._audit_store = audit_store

    def execute(self, call: ToolCall) -> ToolResult:
        definition = self._registry.find(call.name)
        if definition is None:
            return self._result(call.name, "denied", error="unknown tool")
        policy_error = check_tool_policy(definition, call)
        if policy_error is not None:
            return self._result(call.name, "denied", error=policy_error, definition=definition)
        handler = self._handlers.get(call.name)
        if handler is None:
            return self._result(call.name, "accepted", definition=definition)
        try:
            output = handler(call.args)
        except Exception as exc:  # noqa: BLE001
            return self._result(call.name, "failed", error=str(exc), definition=definition)
        return self._result(call.name, "succeeded", output=output, definition=definition)

    def _result(
        self,
        tool_name: str,
        status: str,
        *,
        output: dict[str, object] | None = None,
        error: str | None = None,
        definition: ToolDefinition | None = None,
    ) -> ToolResult:
        audited = bool(definition and definition.audit_required and self._audit_store is not None)
        if audited and self._audit_store is not None:
            self._audit_store.append(make_audit_event("tool.execute", tool_name, status))
        return ToolResult(
            tool_name=tool_name,
            status=status,
            output=output or {},
            error=error,
            audited=audited,
        )


def check_tool_policy(definition: ToolDefinition, call: ToolCall) -> str | None:
    if definition.approval_required and not call.approved:
        return "approval required"
    if _mentions_secret_path(call.args):
        return "secret path denied"
    if definition.name == "web_search":
        provider = call.args.get("provider", "duckduckgo")
        allowed = _allowed_web_providers(definition)
        if not isinstance(provider, str) or provider not in allowed:
            return "web search provider denied"
    return None


def _mentions_secret_path(args: dict[str, object]) -> bool:
    denied_parts = (".env", ".ssh", "private_key", "token")
    return any(
        isinstance(value, str) and any(part in value.lower() for part in denied_parts)
        for value in args.values()
    )


def _allowed_web_providers(definition: ToolDefinition) -> set[str]:
    providers = definition.model_extra.get("providers", {}) if definition.model_extra else {}
    if not isinstance(providers, dict):
        return {"duckduckgo"}
    allowed = providers.get("allowed", [])
    return {str(provider) for provider in allowed} if isinstance(allowed, list) else set()
