from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE_ID = "ai-local-agent-runtime"
SERVICE_DISPLAY_NAME = "AI Local Agent Runtime"
SERVICE_DESCRIPTION = "Local-first AI agent runtime daemon"


def is_windows() -> bool:
    """Return True when running on Windows."""
    return platform.system() == "Windows"


def find_nssm() -> Path | None:
    """Locate the NSSM executable.

    Checks (in order):
    1. The ``NSSM_EXE`` environment variable.
    2. ``nssm`` / ``nssm.exe`` on ``PATH``.
    Returns ``None`` if not found.
    """
    env_path = os.environ.get("NSSM_EXE")
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file():
            return candidate.resolve()
    which = shutil.which("nssm") or shutil.which("nssm.exe")
    if which:
        return Path(which).resolve()
    return None


def require_nssm() -> Path:
    """Like :func:`find_nssm` but raises a friendly error if not found."""
    nssm = find_nssm()
    if nssm is None:
        msg = (
            "NSSM not found. "
            "Install NSSM manually and ensure nssm.exe is on PATH, "
            "or set the NSSM_EXE environment variable."
        )
        raise RuntimeError(msg)
    return nssm


def normalize_workspace(workspace: Path) -> Path:
    """Return the absolute, resolved workspace path."""
    return workspace.resolve()


def build_service_command(workspace: Path) -> list[str]:
    """Build the command line for the service runner.

    Returns a list of arguments suitable for ``nssm install``.
    """
    abs_ws = normalize_workspace(workspace)
    return [
        str(sys.executable),
        "-m",
        "ai_local.cli",
        "daemon",
        "run",
        "--workspace",
        str(abs_ws),
        "--loop",
        "--poll-interval",
        "1.0",
    ]


def run_nssm(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run an NSSM command and return the result.

    Raises :class:`RuntimeError` if NSSM is not found.
    """
    nssm = require_nssm()
    return subprocess.run(
        [str(nssm), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _check_workspace(workspace: Path) -> Path:
    """Validate workspace and return resolved absolute path."""
    abs_ws = normalize_workspace(workspace)
    ai_local_dir = abs_ws / ".ai-local"
    if not ai_local_dir.is_dir():
        raise RuntimeError(
            f"Workspace {abs_ws} has not been initialised. "
            "Run `python -m ai_local.cli init --workspace <path>` first."
        )
    return abs_ws


def install_service(
    workspace: Path,
    repo_root: Path | None = None,
) -> str:
    """Install the daemon as a Windows service via NSSM.

    Returns the stdout from the NSSM commands on success.
    Raises :class:`RuntimeError` on failure.
    """
    if not is_windows():
        raise RuntimeError("Windows only")
    abs_ws = _check_workspace(workspace)
    cmd_parts = build_service_command(abs_ws)
    root = repo_root or Path.cwd().resolve()

    lines: list[str] = []

    # nssm install <service-id> <python> -m ai_local.cli daemon run ...
    # Note: nssm install expects the app path and args as separate arguments
    proc = run_nssm(["install", SERVICE_ID, cmd_parts[0], *cmd_parts[1:]])
    if proc.returncode != 0:
        raise RuntimeError(f"NSSM install failed: {proc.stderr.strip() or proc.stdout.strip()}")
    lines.append(proc.stdout.strip())

    # Configure display name
    proc = run_nssm(["set", SERVICE_ID, "DisplayName", SERVICE_DISPLAY_NAME])
    if proc.returncode != 0:
        raise RuntimeError(f"NSSM set DisplayName failed: {proc.stderr.strip()}")
    lines.append(proc.stdout.strip())

    # Configure description
    proc = run_nssm(["set", SERVICE_ID, "Description", SERVICE_DESCRIPTION])
    if proc.returncode != 0:
        raise RuntimeError(f"NSSM set Description failed: {proc.stderr.strip()}")
    lines.append(proc.stdout.strip())

    # Working directory
    proc = run_nssm(["set", SERVICE_ID, "AppDirectory", str(root)])
    if proc.returncode != 0:
        raise RuntimeError(f"NSSM set AppDirectory failed: {proc.stderr.strip()}")
    lines.append(proc.stdout.strip())

    # Stdout log
    stdout_log = abs_ws / ".ai-local" / "logs" / "service.stdout.log"
    proc = run_nssm(["set", SERVICE_ID, "AppStdout", str(stdout_log)])
    if proc.returncode != 0:
        raise RuntimeError(f"NSSM set AppStdout failed: {proc.stderr.strip()}")
    lines.append(proc.stdout.strip())

    # Stderr log
    stderr_log = abs_ws / ".ai-local" / "logs" / "service.stderr.log"
    proc = run_nssm(["set", SERVICE_ID, "AppStderr", str(stderr_log)])
    if proc.returncode != 0:
        raise RuntimeError(f"NSSM set AppStderr failed: {proc.stderr.strip()}")
    lines.append(proc.stdout.strip())

    return "\n".join(filter(None, lines))


def uninstall_service(workspace: Path) -> str:
    """Remove the Windows service via NSSM.

    Does **not** delete workspace data.
    Returns the stdout from NSSM on success.
    """
    if not is_windows():
        raise RuntimeError("Windows only")
    try:
        proc = run_nssm(["remove", SERVICE_ID, "confirm"])
    except RuntimeError as exc:
        raise RuntimeError(f"Failed to remove service: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"NSSM remove failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def start_service(workspace: Path) -> str:
    """Start the Windows service via NSSM."""
    if not is_windows():
        raise RuntimeError("Windows only")
    try:
        proc = run_nssm(["start", SERVICE_ID])
    except RuntimeError as exc:
        raise RuntimeError(f"Failed to start service: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"NSSM start failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def stop_service(workspace: Path) -> str:
    """Stop the Windows service via NSSM."""
    if not is_windows():
        raise RuntimeError("Windows only")
    try:
        proc = run_nssm(["stop", SERVICE_ID])
    except RuntimeError as exc:
        raise RuntimeError(f"Failed to stop service: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"NSSM stop failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def status_service(workspace: Path) -> str:
    """Query the Windows service status via NSSM.

    Returns a human-readable status string.
    """
    if not is_windows():
        raise RuntimeError("Windows only")
    try:
        proc = run_nssm(["status", SERVICE_ID])
    except RuntimeError as exc:
        raise RuntimeError(f"Failed to query service: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"NSSM status failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()
