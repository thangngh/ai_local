import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass(frozen=True)
class RipgrepMatch:
    file_path: str
    line_number: int
    text: str


def _rg_executable() -> str | None:
    on_path = shutil.which("rg")
    if on_path:
        return on_path
    # If callers run via `.venv/Scripts/python`, PATH may not include `.venv/Scripts`.
    exe = Path(sys.executable).resolve()
    candidate = exe.parent / ("rg.exe" if sys.platform.startswith("win") else "rg")
    return str(candidate) if candidate.exists() else None


def ripgrep_available() -> bool:
    return _rg_executable() is not None


def ripgrep_version() -> str | None:
    if not ripgrep_available():
        return None
    rg = _rg_executable()
    if rg is None:
        return None
    completed = subprocess.run(
        [rg, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
    return first_line.strip() or None


def rg_search(pattern: str, root: Path, timeout_seconds: int = 10) -> str:
    rg = _rg_executable()
    if rg is None:
        msg = "ripgrep (rg) is not installed or not on PATH"
        raise FileNotFoundError(msg)
    completed = subprocess.run(
        [rg, "--line-number", "--no-heading", "--color", "never", pattern],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return completed.stdout


def rg_matches(pattern: str, root: Path, timeout_seconds: int = 10) -> list[RipgrepMatch]:
    return parse_rg_matches(rg_search(pattern, root, timeout_seconds=timeout_seconds))


def parse_rg_matches(output: str) -> list[RipgrepMatch]:
    matches: list[RipgrepMatch] = []
    for line in output.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        file_path, line_number, text = parts
        if not line_number.isdigit():
            continue
        matches.append(RipgrepMatch(file_path=file_path, line_number=int(line_number), text=text))
    return matches
