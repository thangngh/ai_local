import re


_ALIASES = {
    "luong": "flow",
    "luồng": "flow",
    "quyet dinh": "decision",
    "quyết định": "decision",
    "truy hoi": "retrieval",
    "truy hồi": "retrieval",
    "hoi quy": "regression",
    "hồi quy": "regression",
    "kiem lai": "kiem lai",
    "kiếm lai": "kiem lai",
}


def normalize_query(query: str) -> str:
    compact = re.sub(r"[!?]+", " ", query.strip())
    compact = re.sub(r"\s+", " ", compact)
    return compact.casefold()


def bilingual_aliases(query: str) -> list[str]:
    normalized = normalize_query(query)
    aliases = [normalized]
    for term, alias in _ALIASES.items():
        if term in normalized and alias not in aliases:
            aliases.append(alias)
    return aliases
