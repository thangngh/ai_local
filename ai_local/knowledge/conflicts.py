from ai_local.knowledge.models import (
    ConflictCandidate,
    ConflictResolution,
    ConflictType,
)


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
    return ConflictResolution(
        conflict_type=conflict_type,
        candidates=candidates,
        decision="ask_user",
        reason="conflicting instances have no authoritative winner",
    )
