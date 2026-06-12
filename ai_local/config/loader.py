import sys
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        msg = f"Expected YAML mapping in {path}"
        raise ValueError(msg)
    return data


def resolve_config(path: Path, package_rel: str | None = None) -> Path:
    """Resolve a config file path.

    1. If *path* is absolute, use it as-is.
    2. If *path* exists relative to CWD, use it.
    3. If *package_rel* is provided, fall back to ``<package_root>/package_rel``.

    This avoids FileNotFoundError when running from a workspace that does not
    have its own ``configs/`` directory.
    """
    if path.is_absolute():
        return path
    if path.exists():
        return path
    if package_rel is not None:
        from ai_local import __file__ as _pkg_file

        fallback = Path(_pkg_file).parent.parent / package_rel
        if fallback.exists():
            return fallback
    return path  # let the caller handle the error

