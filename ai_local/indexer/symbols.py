import ast
from dataclasses import dataclass
from typing import Protocol

from tree_sitter import Language, Node, Parser


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    start_line: int
    end_line: int


class SymbolExtractor(Protocol):
    def extract(self, content: str) -> list[Symbol]: ...


class PythonAstSymbolExtractor:
    def extract(self, content: str) -> list[Symbol]:
        return extract_python_symbols(content)


@dataclass(frozen=True)
class TreeSitterSymbolExtractor:
    language: Language
    declaration_kinds: dict[str, str]
    name_field: str = "name"

    def extract(self, content: str) -> list[Symbol]:
        parser = Parser(self.language)
        tree = parser.parse(content.encode("utf-8"))
        symbols: list[Symbol] = []
        self._collect_symbols(tree.root_node, content.encode("utf-8"), symbols)
        return sorted(symbols, key=lambda symbol: symbol.start_line)

    def _collect_symbols(self, node: Node, content: bytes, symbols: list[Symbol]) -> None:
        symbol_kind = self.declaration_kinds.get(node.type)
        name_node = node.child_by_field_name(self.name_field)
        if symbol_kind is not None and name_node is not None:
            symbols.append(
                Symbol(
                    name=content[name_node.start_byte : name_node.end_byte].decode("utf-8"),
                    kind=symbol_kind,
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                )
            )
        for child in node.children:
            self._collect_symbols(child, content, symbols)


DEFAULT_SYMBOL_EXTRACTORS: dict[str, SymbolExtractor] = {
    "python": PythonAstSymbolExtractor(),
}


def extract_symbols(
    content: str,
    language: str,
    *,
    extractors: dict[str, SymbolExtractor] | None = None,
) -> list[Symbol]:
    extractor = (extractors or DEFAULT_SYMBOL_EXTRACTORS).get(language)
    return extractor.extract(content) if extractor is not None else []


def extract_python_symbols(content: str) -> list[Symbol]:
    tree = ast.parse(content)
    symbols: list[Symbol] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                Symbol(
                    name=node.name,
                    kind="function",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                )
            )
        if isinstance(node, ast.ClassDef):
            symbols.append(
                Symbol(
                    name=node.name,
                    kind="class",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                )
            )
    return sorted(symbols, key=lambda symbol: symbol.start_line)
