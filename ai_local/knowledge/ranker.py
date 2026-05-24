from ai_local.knowledge.models import EvidenceBand, EvidenceRank, EvidenceSignal

_MAX_UNTRUSTED_AUTHORITY = 10
_MAX_UNKNOWN_AUTHORITY = 8


def calculate_evidence_rank(signal: EvidenceSignal) -> int:
    source_authority = _bounded_source_authority(signal)
    return (
        source_authority
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
        reason=_rank_reason(signal),
    )


def _bounded_source_authority(signal: EvidenceSignal) -> int:
    if signal.noise_type == "unknown_source":
        return min(signal.source_authority, _MAX_UNKNOWN_AUTHORITY)
    if signal.noise_type == "deep_context_noise":
        return min(signal.source_authority, 30)
    if signal.noise_type == "noisy_comments":
        return min(signal.source_authority, 24)
    return signal.source_authority


def _rank_reason(signal: EvidenceSignal) -> str:
    if signal.noise_type == "unknown_source" and signal.source_authority > _MAX_UNKNOWN_AUTHORITY:
        return "unknown source authority capped before rank formula"
    if signal.noise_type == "noisy_comments" and signal.source_authority > 24:
        return "noisy project comments capped before rank formula"
    if signal.source_authority <= _MAX_UNTRUSTED_AUTHORITY:
        return "low authority evidence ranked without promotion"
    return "rank formula applied"


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
