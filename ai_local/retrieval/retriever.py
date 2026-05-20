from pathlib import Path

from ai_local.retrieval.ripgrep import rg_search


def retrieve_exact(query: str, root: Path) -> str:
    return rg_search(query, root)

