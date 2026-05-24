from ai_local.knowledge.models import (
    ConflictCandidate,
    ConflictResolution,
    ConflictType,
)

_RANK_WIN_MARGIN = 12
_MAX_WINNER_RISK = 0.60


def resolve_conflict(
    conflict_type: ConflictType,
    candidates: list[ConflictCandidate],
) -> ConflictResolution:
    if conflict_type in {"no_safe_path", "all_paths_invalid"}:
        return ConflictResolution(
            conflict_type=conflict_type,
            candidates=candidates,
            decision="stop",
            reason="no safe conflicting path can continue",
        )
    if conflict_type == "missing_test_evidence":
        return ConflictResolution(
            conflict_type=conflict_type,
            candidates=candidates,
            decision="defer_until_evidence",
            reason="conflict needs test evidence before decision",
        )
    winner = _clear_winner(candidates)
    if winner is not None and conflict_type in {
        "equal_authority_equal_evidence",
        "multi_instance_tie",
    }:
        return ConflictResolution(
            conflict_type=conflict_type,
            candidates=candidates,
            decision="use_candidate",
            selected_candidate_id=winner.id,
            reason="one candidate has materially stronger evidence and acceptable risk",
        )
    return ConflictResolution(
        conflict_type=conflict_type,
        candidates=candidates,
        decision="ask_user",
        reason="conflicting instances have no authoritative winner",
    )


def _clear_winner(candidates: list[ConflictCandidate]) -> ConflictCandidate | None:
    ranked = sorted(candidates, key=lambda candidate: candidate.evidence_rank, reverse=True)
    winner = ranked[0]
    runner_up = ranked[1]
    if winner.risk > _MAX_WINNER_RISK:
        return None
    if winner.evidence_rank - runner_up.evidence_rank < _RANK_WIN_MARGIN:
        return None
    if winner.authority != runner_up.authority and not winner.authority.startswith("K"):
        return None
    return winner
