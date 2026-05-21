from ai_local.knowledge.models import EvidenceBand, EvidenceRank, EvidenceSignal


def calculate_evidence_rank(signal: EvidenceSignal) -> int:
    return (
        signal.source_authority
        + signal.evidence_strength
        + signal.freshness
        + signal.project_relevance
        + signal.confirmation_weight
        - signal.conflict_penalty
        - signal.staleness_penalty
    )


def rank_evidence(signal: EvidenceSignal) -> EvidenceRank:
    if signal.noise_type in {
        "prompt_injection",
        "policy_laundering",
        "repeated_untrusted_claim",
    }:
        return EvidenceRank(
            signal=signal,
            rank=calculate_evidence_rank(signal),
            band="reject",
            reason="hard reject evidence noise",
        )

    rank = calculate_evidence_rank(signal)
    return EvidenceRank(
        signal=signal,
        rank=rank,
        band=_rank_band(rank),
        reason="rank formula applied",
    )


def _rank_band(rank: int) -> EvidenceBand:
    if rank >= 90:
        return "canonical"
    if rank >= 75:
        return "strong"
    if rank >= 60:
        return "caution"
    if rank >= 40:
        return "weak"
    return "reject"
