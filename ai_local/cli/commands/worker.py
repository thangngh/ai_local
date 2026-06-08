from pathlib import Path
import typer
from ai_local.runtime.worker_contract import run_worker_once, WorkerResult



worker_app = typer.Typer()

@worker_app.command("run")
def worker_run(
    once: bool = typer.Option(False, "--once"),
    loop: bool = typer.Option(False, "--loop"),
    workspace: Path = typer.Option(Path('.'), "--workspace", "-w"),
) -> None:
    """Run the worker.

    * ``--once`` processes a single job (or none) and exits.
    * ``--loop`` processes jobs continuously until interrupted.
    The original CLI printed ``WORKER ran``/``idle``; now we emit the
    contract‑specified format.
    """
    if once:
        result = run_worker_once(workspace)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        raise typer.Exit(code=0)

    # ``--loop`` mode (not part of Phase 4A but retained for compatibility)
    while True:
        result = run_worker_once(workspace)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        if not loop:
            break
