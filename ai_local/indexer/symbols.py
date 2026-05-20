from dataclasses import dataclass


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    start_line: int
    end_line: int

