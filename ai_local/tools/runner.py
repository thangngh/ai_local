import subprocess
from pathlib import Path


def run_argv(argv: list[str], cwd: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        timeout=timeout_seconds,
        capture_output=True,
        text=True,
        check=False,
    )

