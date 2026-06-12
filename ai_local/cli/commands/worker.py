from pathlib import Path
import typer
from ai_local.llm.ollama import OllamaError
from ai_local.runtime.ollama_worker import build_worker_ollama_client
from ai_local.runtime.worker_contract import run_worker_once, WorkerResult



worker_app = typer.Typer()

@worker_app.command("run")
def worker_run(
    once: bool = typer.Option(False, "--once"),
    loop: bool = typer.Option(False, "--loop"),
    workspace: Path = typer.Option(Path('.'), "--workspace", "-w"),
    ollama: bool = typer.Option(False, "--ollama", help="Use Ollama to generate code_change proposals."),
    ollama_model: str | None = typer.Option(None, "--ollama-model"),
    ollama_base_url: str | None = typer.Option(None, "--ollama-base-url"),
) -> None:
    """Run the worker.

    * ``--once`` processes a single job (or none) and exits.
    * ``--loop`` processes jobs continuously until interrupted.
    The original CLI printed ``WORKER ran``/``idle``; now we emit the
    contract‑specified format.
    """
    try:
        ollama_client = build_worker_ollama_client(
            workspace=workspace,
            enabled=ollama,
            model=ollama_model,
            base_url=ollama_base_url,
        )
    except OllamaError as exc:
        typer.echo(f"WORKER ollama FAIL reason=\"{exc}\"")
        raise typer.Exit(code=1) from exc
    if ollama_client is not None:
        typer.echo(f"WORKER ollama model={ollama_client.model}")
    if once:
        result = run_worker_once(workspace, ollama_client=ollama_client)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        raise typer.Exit(code=0)

    # ``--loop`` mode (not part of Phase 4A but retained for compatibility)
    while True:
        result = run_worker_once(workspace, ollama_client=ollama_client)
        if result.status == "pass":
            typer.echo(f"WORKER once PASS processed={result.processed} job_id={result.job_id}")
        else:
            typer.echo(f"WORKER once SKIP processed={result.processed} reason=\"{result.reason}\"")
        if not loop:
            break
