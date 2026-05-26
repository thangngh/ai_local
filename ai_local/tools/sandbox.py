from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol


SandboxBackend = Literal["subprocess", "docker", "bubblewrap"]
SandboxDecision = Literal["succeeded", "failed", "timed_out", "denied"]

_SHELL_METACHARACTERS = frozenset({"&&", "||", "|", ";", ">", ">>", "<", "$(", "`"})


@dataclass(frozen=True)
class SandboxPolicy:
    workspace_root: Path
    backend: SandboxBackend = "subprocess"
    max_timeout_seconds: int = 120
    allowed_executables: frozenset[str] = field(default_factory=frozenset)
    allow_shell: bool = False
    deny_shell_metacharacters: bool = True
    network_enabled: bool = False
    writable_roots: tuple[Path, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SandboxRunRequest:
    command: list[str]
    cwd: Path
    timeout_seconds: int
    policy: SandboxPolicy


@dataclass(frozen=True)
class SandboxRunResult:
    decision: SandboxDecision
    reason: str
    command: list[str]
    cwd: str | None = None
    timeout_seconds: int | None = None
    stdout: str = ""
    stderr: str = ""
    return_code: int | None = None
    backend: SandboxBackend = "subprocess"


class ToolSandboxAdapter(Protocol):
    def run(self, request: SandboxRunRequest) -> SandboxRunResult:
        """Run a command through a sandbox backend or return a deny decision."""


class SubprocessSandboxAdapter:
    """Deny-by-default subprocess adapter for local tool execution."""

    def run(self, request: SandboxRunRequest) -> SandboxRunResult:
        preflight = validate_sandbox_request(request)
        if preflight is not None:
            return preflight
        if request.policy.backend != "subprocess":
            return planned_backend_denial(request)

        try:
            completed = subprocess.run(  # noqa: S603
                request.command,
                cwd=request.cwd,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return SandboxRunResult(
                decision="timed_out",
                reason="sandbox subprocess timed out",
                command=request.command,
                cwd=str(request.cwd),
                timeout_seconds=request.timeout_seconds,
                stdout=exc.stdout if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr if isinstance(exc.stderr, str) else "",
                backend=request.policy.backend,
            )

        return SandboxRunResult(
            decision="succeeded" if completed.returncode == 0 else "failed",
            reason=(
                "sandbox subprocess succeeded"
                if completed.returncode == 0
                else "sandbox subprocess failed"
            ),
            command=request.command,
            cwd=str(request.cwd),
            timeout_seconds=request.timeout_seconds,
            stdout=completed.stdout,
            stderr=completed.stderr,
            return_code=completed.returncode,
            backend=request.policy.backend,
        )


def validate_sandbox_request(request: SandboxRunRequest) -> SandboxRunResult | None:
    policy = request.policy
    workspace_root = policy.workspace_root.resolve()
    cwd = request.cwd.resolve()
    if not _is_relative_to(cwd, workspace_root):
        return _denied(request, "sandbox cwd escapes workspace root")
    if not request.command:
        return _denied(request, "sandbox command is empty", cwd=cwd)
    if policy.allow_shell:
        return _denied(request, "sandbox shell execution is disabled", cwd=cwd)
    if request.timeout_seconds < 1:
        return _denied(request, "sandbox timeout must be positive", cwd=cwd)
    if request.timeout_seconds > policy.max_timeout_seconds:
        return _denied(request, "sandbox timeout exceeds policy cap", cwd=cwd)

    executable = request.command[0]
    allowed = policy.allowed_executables
    if allowed and executable not in allowed and Path(executable).name not in allowed:
        return _denied(request, "sandbox executable is not allowlisted", cwd=cwd)

    if policy.deny_shell_metacharacters:
        for part in request.command:
            if _contains_shell_metacharacter(part):
                return _denied(request, "sandbox command contains shell metacharacter", cwd=cwd)
    return None


def planned_backend_denial(request: SandboxRunRequest) -> SandboxRunResult:
    return _denied(
        request,
        f"sandbox backend {request.policy.backend} is not configured",
        cwd=request.cwd.resolve(),
    )


def build_tool_sandbox_policy(
    *,
    workspace_root: Path,
    command: list[str],
    timeout_seconds: int,
    backend: SandboxBackend = "subprocess",
) -> SandboxPolicy:
    executable = command[0] if command else ""
    return SandboxPolicy(
        workspace_root=workspace_root,
        backend=backend,
        max_timeout_seconds=timeout_seconds,
        allowed_executables=frozenset({executable, Path(executable).name} if executable else set()),
    )


def _denied(
    request: SandboxRunRequest,
    reason: str,
    *,
    cwd: Path | None = None,
) -> SandboxRunResult:
    return SandboxRunResult(
        decision="denied",
        reason=reason,
        command=request.command,
        cwd=str(cwd) if cwd is not None else None,
        timeout_seconds=request.timeout_seconds,
        backend=request.policy.backend,
    )


def _contains_shell_metacharacter(part: str) -> bool:
    return part in _SHELL_METACHARACTERS or any(token in part for token in ("&&", "||", "$(", "`"))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
