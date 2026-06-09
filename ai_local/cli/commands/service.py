from __future__ import annotations

from pathlib import Path

import typer

service_app = typer.Typer()

SERVICE_ID = "ai-local-agent-runtime"
SERVICE_DISPLAY_NAME = "AI Local Agent Runtime"


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


@service_app.command("install")
def service_install_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
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


@service_app.command("uninstall")
def service_uninstall_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
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


@service_app.command("start")
def service_start_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
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


@service_app.command("stop")
def service_stop_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
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


@service_app.command("status")
def service_status_group(
    dry_run: bool = typer.Option(False, "--dry-run"),
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
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
