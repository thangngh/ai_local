from __future__ import annotations

import typer
from pathlib import Path
from typing import Optional

from ai_local.runtime.daemon_contract import (
    append_daemon_log,
    daemon_lock_ok,
    daemon_timestamp,
    run_daemon_loop,
)
from ai_local.runtime.worker_contract import ensure_workspace, run_worker_once

daemon_app = typer.Typer()


@daemon_app.command("run")
def daemon_run(
    workspace: Path = typer.Option(Path("."), "--workspace", "-w"),
    once: bool = typer.Option(False, "--once"),
    loop: bool = typer.Option(False, "--loop"),
    poll_interval: float = typer.Option(0.1, "--poll-interval"),
    max_iterations: Optional[int] = typer.Option(None, "--max-iterations"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Run the daemon.

    * ``--once`` processes a single job and exits.
    * ``--loop`` continuously processes jobs with optional ``--poll-interval``
      and ``--max-iterations``.
    * ``--force`` bypasses a stale lock.
    """
    ensure_workspace(workspace)
    mode = "loop" if loop else "once"

    # --- lock check ---------------------------------------------------------
    if not daemon_lock_ok(workspace, force=force):
        typer.echo("Daemon already running (lock present). Use --force to override.")
        raise typer.Exit(code=1)

    # --- once mode ----------------------------------------------------------
    if once:
        typer.echo("DAEMON run mode=once")
        result = run_worker_once(workspace)
        if result.status == "pass":
            typer.echo(
                f"WORKER once PASS processed={result.processed} "
                f"job_id={result.job_id}"
            )
        else:
            typer.echo(
                f"WORKER once SKIP processed={result.processed} "
                f'reason="{result.reason}"'
            )
        append_daemon_log(
            workspace,
            {
                "timestamp": daemon_timestamp(),
                "component": "daemon",
                "mode": "once",
                "worker": {
                    "status": result.status,
                    "processed": result.processed,
                    "job_id": result.job_id,
                    "reason": result.reason,
                },
            },
        )
        typer.echo(f"LOG {_log_path(workspace)}")
        return

    # --- loop mode ----------------------------------------------------------
    if not loop:
        typer.echo("No operation specified. Use --once or --loop.")
        raise typer.Exit(code=1)

    iteration = run_daemon_loop(
        workspace=workspace,
        poll_interval=poll_interval,
        max_iterations=max_iterations,
        emit_line=typer.echo,
    )
    typer.echo(f"LOG {_log_path(workspace)}")


def _log_path(workspace: Path) -> Path:
    paths = ensure_workspace(workspace)
    return paths["logs"] / "daemon.log"
