from __future__ import annotations

from pathlib import Path

import typer

service_app = typer.Typer()

SERVICE_ID = "ai-local-agent-runtime"
SERVICE_DISPLAY_NAME = "AI Local Agent Runtime"

PYWIN32_SERVICE_ID = "ai-local-agent-runtime-pywin32"
PYWIN32_SERVICE_DISPLAY_NAME = "AI Local Agent Runtime (pywin32)"


def _workspace_dir(workspace: Path) -> Path:
    return workspace / ".ai-local"


def _ensure_workspace(workspace: Path) -> dict[str, Path]:
    base = _workspace_dir(workspace)
    dirs = {
        "base": base,
        "logs": base / "logs",
        "reports": base / "reports",
        "backups": base / "backups",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return {
        **dirs,
        "config": base / "config.yaml",
        "knowledge_db": base / "knowledge.db",
        "runtime_db": base / "runtime.db",
        "tasks_db": base / "tasks.db",
        "audit_db": base / "audit.db",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_nssm_or_fail() -> None:
    """Check that NSSM is available; exit with error if not."""
    try:
        from ai_local.runtime.windows_service import require_nssm

        require_nssm()
    except (ImportError, RuntimeError) as exc:
        typer.echo(f"SERVICE install FAIL reason=\"{exc}\"")
        typer.echo("HINT install NSSM manually and ensure nssm.exe is on PATH or set NSSM_EXE")
        raise typer.Exit(code=1) from exc


def _check_windows() -> None:
    """Exit with error if not on Windows."""
    from ai_local.runtime.windows_service import is_windows

    if not is_windows():
        typer.echo("SERVICE install FAIL reason=\"Windows only\"")
        raise typer.Exit(code=1)


def _check_pywin32() -> None:
    """Exit with error if pywin32 is not available."""
    from ai_local.runtime.pywin32_service import pywin32_available

    if not pywin32_available():
        typer.echo(
            "SERVICE install FAIL reason=\"pywin32 not found. "
            'Install with: python -m pip install pywin32"'
        )
        typer.echo("HINT install pywin32 with: python -m pip install pywin32")
        raise typer.Exit(code=1)


def _is_pywin32(strategy: str) -> bool:
    return strategy == "pywin32"


def _resolve_workspace(workspace: Path) -> Path:
    """Return resolved absolute workspace path, creating .ai-local dirs."""
    _ensure_workspace(workspace)
    return workspace.resolve()


# ── Install ───────────────────────────────────────────────────────────────────


@service_app.command("install")
def service_install_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    strategy: str = typer.Option("nssm", "--strategy"),
) -> None:
    if _is_pywin32(strategy):
        _pywin32_install(dry_run, workspace)
    else:
        _nssm_install(dry_run, workspace)


def _nssm_install(dry_run: bool, workspace: Path) -> None:
    if dry_run:
        _ensure_workspace(workspace)
        typer.echo("SERVICE install dry-run")
        typer.echo("NAME AI Local Agent Runtime")
        typer.echo(
            f"COMMAND python -m ai_local.cli daemon run "
            f"--workspace {workspace} --loop --poll-interval 1.0"
        )
        typer.echo("NOTE dry-run only; no Windows service was created")
        return

    _check_windows()
    _load_nssm_or_fail()

    try:
        from ai_local.runtime.windows_service import install_service, normalize_workspace

        abs_ws = normalize_workspace(workspace)
        install_service(abs_ws)
        typer.echo("SERVICE install PASS")
        typer.echo(f"NAME {SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {SERVICE_ID}")
        typer.echo(
            f"COMMAND python -m ai_local.cli daemon run "
            f"--workspace {abs_ws} --loop --poll-interval 1.0"
        )
    except RuntimeError as exc:
        typer.echo(f"SERVICE install FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


def _pywin32_install(dry_run: bool, workspace: Path) -> None:
    abs_ws = _resolve_workspace(workspace)

    if dry_run:
        typer.echo("SERVICE install dry-run")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo(
            f"COMMAND python -m ai_local.runtime.pywin32_service "
            f"install --workspace {abs_ws}"
        )
        typer.echo("NOTE dry-run only; no Windows service was created")
        return

    _check_windows()
    _check_pywin32()

    try:
        from ai_local.runtime.pywin32_service import install_pywin32_service

        install_pywin32_service(abs_ws, startup="manual")
        typer.echo("SERVICE install PASS")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo(f"WORKSPACE {abs_ws}")
    except RuntimeError as exc:
        typer.echo(f"SERVICE install FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


# ── Uninstall ─────────────────────────────────────────────────────────────────


@service_app.command("uninstall")
def service_uninstall_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    strategy: str = typer.Option("nssm", "--strategy"),
) -> None:
    if _is_pywin32(strategy):
        _pywin32_uninstall(dry_run)
    else:
        _nssm_uninstall(dry_run, workspace)


def _nssm_uninstall(dry_run: bool, workspace: Path) -> None:
    if dry_run:
        typer.echo("SERVICE uninstall dry-run")
        typer.echo("NAME AI Local Agent Runtime")
        typer.echo("NOTE dry-run only; no Windows service was removed")
        return

    _check_windows()
    _load_nssm_or_fail()

    try:
        from ai_local.runtime.windows_service import uninstall_service

        uninstall_service(workspace)
        typer.echo("SERVICE uninstall PASS")
        typer.echo(f"NAME {SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {SERVICE_ID}")
        typer.echo("NOTE workspace data was not removed")
    except RuntimeError as exc:
        typer.echo(f"SERVICE uninstall FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


def _pywin32_uninstall(dry_run: bool) -> None:
    if dry_run:
        typer.echo("SERVICE uninstall dry-run")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo(
            "COMMAND python -m ai_local.runtime.pywin32_service remove"
        )
        typer.echo("NOTE dry-run only; no Windows service was removed")
        return

    _check_windows()
    _check_pywin32()

    try:
        from ai_local.runtime.pywin32_service import remove_pywin32_service

        remove_pywin32_service()
        typer.echo("SERVICE uninstall PASS")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo("NOTE workspace data was not removed")
    except RuntimeError as exc:
        typer.echo(f"SERVICE uninstall FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


# ── Start ─────────────────────────────────────────────────────────────────────


@service_app.command("start")
def service_start_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    strategy: str = typer.Option("nssm", "--strategy"),
) -> None:
    if _is_pywin32(strategy):
        _pywin32_start(dry_run)
    else:
        _nssm_start(dry_run, workspace)


def _nssm_start(dry_run: bool, workspace: Path) -> None:
    if dry_run:
        typer.echo("SERVICE start dry-run")
        typer.echo("NAME AI Local Agent Runtime")
        typer.echo("COMMAND <service-start-command-placeholder>")
        typer.echo("NOTE dry-run only; no Windows service was started")
        return

    _check_windows()
    _load_nssm_or_fail()

    try:
        from ai_local.runtime.windows_service import start_service

        start_service(workspace)
        typer.echo("SERVICE start PASS")
        typer.echo(f"NAME {SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {SERVICE_ID}")
    except RuntimeError as exc:
        typer.echo(f"SERVICE start FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


def _pywin32_start(dry_run: bool) -> None:
    if dry_run:
        typer.echo("SERVICE start dry-run")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo("COMMAND python -m ai_local.runtime.pywin32_service start")
        typer.echo("NOTE dry-run only; no Windows service was started")
        return

    _check_windows()
    _check_pywin32()

    try:
        from ai_local.runtime.pywin32_service import start_pywin32_service

        start_pywin32_service()
        typer.echo("SERVICE start PASS")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
    except RuntimeError as exc:
        typer.echo(f"SERVICE start FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


# ── Stop ──────────────────────────────────────────────────────────────────────


@service_app.command("stop")
def service_stop_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    strategy: str = typer.Option("nssm", "--strategy"),
) -> None:
    if _is_pywin32(strategy):
        _pywin32_stop(dry_run)
    else:
        _nssm_stop(dry_run, workspace)


def _nssm_stop(dry_run: bool, workspace: Path) -> None:
    if dry_run:
        typer.echo("SERVICE stop dry-run")
        typer.echo("NAME AI Local Agent Runtime")
        typer.echo("NOTE dry-run only; no Windows service was stopped")
        return

    _check_windows()
    _load_nssm_or_fail()

    try:
        from ai_local.runtime.windows_service import stop_service

        stop_service(workspace)
        typer.echo("SERVICE stop PASS")
        typer.echo(f"NAME {SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {SERVICE_ID}")
    except RuntimeError as exc:
        typer.echo(f"SERVICE stop FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


def _pywin32_stop(dry_run: bool) -> None:
    if dry_run:
        typer.echo("SERVICE stop dry-run")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo("COMMAND python -m ai_local.runtime.pywin32_service stop")
        typer.echo("NOTE dry-run only; no Windows service was stopped")
        return

    _check_windows()
    _check_pywin32()

    try:
        from ai_local.runtime.pywin32_service import stop_pywin32_service

        stop_pywin32_service()
        typer.echo("SERVICE stop PASS")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
    except RuntimeError as exc:
        typer.echo(f"SERVICE stop FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


# ── Status ────────────────────────────────────────────────────────────────────


@service_app.command("status")
def service_status_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    strategy: str = typer.Option("nssm", "--strategy"),
) -> None:
    if _is_pywin32(strategy):
        _pywin32_status(dry_run)
    else:
        _nssm_status(dry_run, workspace)


def _nssm_status(dry_run: bool, workspace: Path) -> None:
    if dry_run:
        typer.echo("SERVICE status dry-run")
        typer.echo("NAME AI Local Agent Runtime")
        typer.echo("NOTE dry-run only; no Windows service was queried")
        return

    _check_windows()
    _load_nssm_or_fail()

    try:
        from ai_local.runtime.windows_service import status_service

        raw = status_service(workspace)
        typer.echo("SERVICE status")
        typer.echo(f"NAME {SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {SERVICE_ID}")
        typer.echo(f"STATE {raw.strip()}")
    except RuntimeError as exc:
        typer.echo(f"SERVICE status FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


def _pywin32_status(dry_run: bool) -> None:
    if dry_run:
        typer.echo("SERVICE status dry-run")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo("NOTE dry-run only; no Windows service was queried")
        return

    _check_windows()
    _check_pywin32()

    try:
        from ai_local.runtime.pywin32_service import status_pywin32_service

        state = status_pywin32_service()
        typer.echo("SERVICE status")
        typer.echo("STRATEGY pywin32")
        typer.echo(f"NAME {PYWIN32_SERVICE_DISPLAY_NAME}")
        typer.echo(f"ID {PYWIN32_SERVICE_ID}")
        typer.echo(f"STATE {state}")
    except RuntimeError as exc:
        typer.echo(f"SERVICE status FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc


# ── Logs (cross-platform, shared) ─────────────────────────────────────────────


@service_app.command("logs")
def service_logs_group(
    tail: int = typer.Option(None, "--tail"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Print daemon/service log lines (cross-platform)."""
    paths = _ensure_workspace(workspace)
    log_candidates = [
        ("daemon.log", paths["logs"] / "daemon.log"),
        ("service.stdout.log", paths["logs"] / "service.stdout.log"),
        ("service.stderr.log", paths["logs"] / "service.stderr.log"),
    ]

    found = False
    for name, log_path in log_candidates:
        if log_path.exists():
            if not found:
                found = True
            lines = log_path.read_text(encoding="utf-8").strip().splitlines()
            tail_count = tail if tail is not None else len(lines)
            tail_lines = lines[-tail_count:] if tail_count > 0 else lines
            typer.echo(f"LOGS {log_path} tail={tail_count}")
            for line in tail_lines:
                typer.echo(line)

    if not found:
        typer.echo(f"LOGS none path={paths['logs']}")
