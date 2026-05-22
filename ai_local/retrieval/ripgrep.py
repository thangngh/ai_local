import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RipgrepMatch:
    file_path: str
    line_number: int
    text: str


def rg_search(pattern: str, root: Path, timeout_seconds: int = 10) -> str:
    completed = subprocess.run(
        ["rg", "--line-number", "--no-heading", "--color", "never", pattern],
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
