from dataclasses import dataclass, field
from typing import Literal


RetrievalDecision = Literal["continue", "verify", "ask_user", "quarantine", "stop"]


@dataclass(frozen=True)
class RetrievalQuery:
    raw: str
    normalized: str
    aliases: list[str]


@dataclass(frozen=True)
class RetrievalHit:
    source_id: str
    source_ref: str
    content_hash: str
    text: str
    source_type: str
    lexical_score: float
    evidence_strength: float = 0.0
    flow_match: float = 0.0
    source_authority: float = 0.0
    freshness: float = 1.0
    interference: float = 0.0
    flags: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return (
            0.20 * self.lexical_score
            + 0.20 * self.flow_match
            + 0.15 * self.evidence_strength
            + 0.10 * self.source_authority
            + 0.10 * self.freshness
            - 0.25 * self.interference
        )

    @property
    def usable(self) -> bool:
        return not any(
            flag in {"prompt_injection", "deep_policy_shadowing", "deep_chain_interference"}
            for flag in self.flags
        )


@dataclass(frozen=True)
class ContextPackage:
    query: RetrievalQuery
    hits: list[RetrievalHit]
    selected_hits: list[RetrievalHit]
    rejected_hits: list[RetrievalHit]
    decision: RetrievalDecision
    reason: str

    @property
    def evidence_refs(self) -> list[str]:
        return [hit.source_ref for hit in self.selected_hits]
