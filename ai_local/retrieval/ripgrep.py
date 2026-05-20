import subprocess
from pathlib import Path


def rg_search(pattern: str, root: Path, timeout_seconds: int = 10) -> str:
    completed = subprocess.run(
        ["rg", pattern],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return completed.stdout

