from __future__ import annotations
from pathlib import Path

from ai_local.audit.store import InMemoryAuditStore, make_audit_event
from ai_local.skills.models import (
    SkillNextGate,
    SkillScriptRunDecision,
    SkillScriptRunRequest,
    SkillScriptRunResult,
)
from ai_local.skills.runtime import evaluate_skill_script
from ai_local.tools.registry import ToolRegistry
from ai_local.tools.sandbox import (
    SandboxRunRequest,
    SubprocessSandboxAdapter,
    ToolSandboxAdapter,
    build_tool_sandbox_policy,
)


class SkillScriptRunner:
    def __init__(
        self,
        tools: ToolRegistry,
        *,
        workspace_root: Path,
        audit_store: InMemoryAuditStore | None = None,
        sandbox: ToolSandboxAdapter | None = None,
    ) -> None:
        self._tools = tools
        self._workspace_root = workspace_root.resolve()
        self._audit_store = audit_store
        self._sandbox = sandbox or SubprocessSandboxAdapter()

    def run(self, request: SkillScriptRunRequest) -> SkillScriptRunResult:
        policy = evaluate_skill_script(request.script, tools=self._tools)
        if policy.decision != "allow":
            result = _run_result(
                request,
                _policy_decision(policy.decision),
                policy.reason,
                next_gate=policy.next_gate,
            )
            self._audit(result)
            return result

        tool = self._tools.find(request.script.tool_name)
        if tool is None:
            result = _run_result(
                request,
                "denied",
                "script tool is not registered",
                next_gate="tool_registry",
            )
            self._audit(result)
            return result
        command = _tool_command(tool.model_extra.get("command") if tool.model_extra else None)
        if not command:
            result = _run_result(
                request,
                "denied",
                "script tool has no subprocess command",
                next_gate="tool_registry",
            )
            self._audit(result)
            return result

        cwd = self._resolve_cwd(request.cwd)
        if cwd is None:
            result = _run_result(
                request,
                "denied",
                "script cwd escapes workspace root",
                command=[*command, *request.argv],
                next_gate="stop",
            )
            self._audit(result)
            return result

        timeout_seconds = min(request.timeout_seconds or tool.timeout_seconds, tool.timeout_seconds)
        full_command = [*command, *request.argv]
        sandbox_result = self._sandbox.run(
            SandboxRunRequest(
                command=full_command,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                policy=build_tool_sandbox_policy(
                    workspace_root=self._workspace_root,
                    command=command,
                    timeout_seconds=tool.timeout_seconds,
                ),
            )
        )
        if sandbox_result.decision == "timed_out":
            result = _run_result(
                request,
                "timed_out",
                "script subprocess timed out",
                command=full_command,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                stdout=sandbox_result.stdout,
                stderr=sandbox_result.stderr,
                next_gate="patch_pipeline",
            )
            self._audit(result)
            return result
        if sandbox_result.decision == "denied":
            result = _run_result(
                request,
                "denied",
                sandbox_result.reason,
                command=full_command,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                next_gate="stop",
            )
            self._audit(result)
            return result

        decision: SkillScriptRunDecision = (
            "succeeded" if sandbox_result.decision == "succeeded" else "failed"
        )
        reason = (
            "script subprocess succeeded"
            if decision == "succeeded"
            else "script subprocess failed"
        )
        next_gate: SkillNextGate = "evidence_rank" if decision == "succeeded" else "patch_pipeline"
        result = _run_result(
            request,
            decision,
            reason,
            command=full_command,
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            stdout=sandbox_result.stdout,
            stderr=sandbox_result.stderr,
            return_code=sandbox_result.return_code,
            next_gate=next_gate,
        )
        self._audit(result)
        return result

    def _resolve_cwd(self, cwd: str | None) -> Path | None:
        resolved = (self._workspace_root / cwd).resolve() if cwd is not None else self._workspace_root
        if not _is_relative_to(resolved, self._workspace_root):
            return None
        return resolved

    def _audit(self, result: SkillScriptRunResult) -> None:
        if self._audit_store is not None:
            self._audit_store.append(
                make_audit_event(
                    "skill.script.run",
                    f"{result.package_id or 'unknown-package'}:{result.script_id}",
                    result.decision,
                )
            )


def _tool_command(command: object) -> list[str]:
    if not isinstance(command, list):
        return []
    return [str(part) for part in command if isinstance(part, str)]


def _policy_decision(decision: str) -> SkillScriptRunDecision:
    if decision == "ask_user":
        return "ask_user"
    if decision == "quarantine":
        return "quarantine"
    return "denied"


def _run_result(
    request: SkillScriptRunRequest,
    decision: SkillScriptRunDecision,
    reason: str,
    *,
    next_gate: SkillNextGate,
    command: list[str] | None = None,
    cwd: Path | None = None,
    timeout_seconds: int | None = None,
    stdout: str = "",
    stderr: str = "",
    return_code: int | None = None,
) -> SkillScriptRunResult:
    return SkillScriptRunResult(
        package_id=request.script.package.package_id,
        script_id=request.script.script_id,
        tool_name=request.script.tool_name,
        decision=decision,
        reason=reason,
        command=command or [],
        cwd=str(cwd) if cwd is not None else None,
        timeout_seconds=timeout_seconds,
        stdout=stdout,
        stderr=stderr,
        return_code=return_code,
        audit_required=True,
        next_gate=next_gate,
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
