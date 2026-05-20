from pathlib import Path


def scan_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()]

