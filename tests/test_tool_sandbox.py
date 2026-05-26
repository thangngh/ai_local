import sys
from pathlib import Path
from typing import cast

from ai_local.tools.sandbox import (
    SandboxBackend,
    SandboxPolicy,
    SandboxRunRequest,
    SubprocessSandboxAdapter,
)


def _request(
    tmp_path: Path,
    command: list[str],
    *,
    timeout_seconds: int = 5,
    max_timeout_seconds: int = 10,
    allowed_executables: frozenset[str] | None = None,
    cwd: Path | None = None,
    backend: str = "subprocess",
) -> SandboxRunRequest:
    return SandboxRunRequest(
        command=command,
        cwd=cwd or tmp_path,
        timeout_seconds=timeout_seconds,
        policy=SandboxPolicy(
            workspace_root=tmp_path,
            backend=cast(SandboxBackend, backend),
            max_timeout_seconds=max_timeout_seconds,
            allowed_executables=allowed_executables
            if allowed_executables is not None
            else frozenset({sys.executable, Path(sys.executable).name}),
        ),
    )


def test_subprocess_sandbox_runs_allowlisted_command(tmp_path: Path) -> None:
    result = SubprocessSandboxAdapter().run(
        _request(tmp_path, [sys.executable, "-c", "print('sandbox-ok')"])
    )

    assert result.decision == "succeeded"
    assert result.return_code == 0
    assert result.stdout.strip() == "sandbox-ok"
    assert result.backend == "subprocess"


def test_subprocess_sandbox_denies_escape_empty_and_unlisted_command(tmp_path: Path) -> None:
    adapter = SubprocessSandboxAdapter()

    escape = adapter.run(_request(tmp_path, [sys.executable, "-c", "print(1)"], cwd=tmp_path.parent))
    empty = adapter.run(_request(tmp_path, []))
    unlisted = adapter.run(
        _request(
            tmp_path,
            [sys.executable, "-c", "print(1)"],
            allowed_executables=frozenset({"rg"}),
        )
    )

    assert escape.decision == "denied"
    assert escape.reason == "sandbox cwd escapes workspace root"
    assert empty.decision == "denied"
    assert empty.reason == "sandbox command is empty"
    assert unlisted.decision == "denied"
    assert unlisted.reason == "sandbox executable is not allowlisted"


def test_subprocess_sandbox_denies_shell_metacharacter_and_timeout_cap(
    tmp_path: Path,
) -> None:
    adapter = SubprocessSandboxAdapter()

    shell_like = adapter.run(_request(tmp_path, [sys.executable, "-c", "print('x') && whoami"]))
    too_long = adapter.run(
        _request(
            tmp_path,
            [sys.executable, "-c", "print(1)"],
            timeout_seconds=20,
            max_timeout_seconds=5,
        )
    )

    assert shell_like.decision == "denied"
    assert shell_like.reason == "sandbox command contains shell metacharacter"
    assert too_long.decision == "denied"
    assert too_long.reason == "sandbox timeout exceeds policy cap"


def test_subprocess_sandbox_times_out(tmp_path: Path) -> None:
    result = SubprocessSandboxAdapter().run(
        _request(
            tmp_path,
            [sys.executable, "-c", "import time; time.sleep(3)"],
            timeout_seconds=1,
            max_timeout_seconds=2,
        )
    )

    assert result.decision == "timed_out"
    assert result.reason == "sandbox subprocess timed out"
    assert result.return_code is None


def test_planned_isolation_backends_fail_closed_until_configured(tmp_path: Path) -> None:
    result = SubprocessSandboxAdapter().run(
        _request(tmp_path, [sys.executable, "-c", "print(1)"], backend="bubblewrap")
    )

    assert result.decision == "denied"
    assert result.reason == "sandbox backend bubblewrap is not configured"
