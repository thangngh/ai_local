from ai_local.memory.models import (
    MemoryDocMatchSignal,
    MemoryRegressionResult,
    RegressionDecision,
)


def doc_match_score(signal: MemoryDocMatchSignal) -> float:
    return (
        0.30 * signal.semantic_match
        + 0.25 * signal.flow_match
        + 0.20 * signal.evidence_match
        + 0.15 * signal.scope_match
        - 0.10 * signal.interference
    )


def state_hops(pattern: str) -> int:
    states = _states(pattern)
    return sum(1 for previous, current in zip(states, states[1:]) if previous != current)


def evaluate_regression(
    *,
    pattern: str,
    signal: MemoryDocMatchSignal,
    constraints_restored: int,
    constraints_required: int,
) -> MemoryRegressionResult:
    score = doc_match_score(signal)
    decision: RegressionDecision
    if signal.laundered:
        decision = "reject_laundered_match"
    elif signal.conflicted:
        decision = "verify_before_use"
    else:
        decision = "restore"
    states = _states(pattern)
    active_state = states[-1] if states else "unknown"
    return MemoryRegressionResult(
        active_state=active_state,
        state_hops=state_hops(pattern),
        doc_match_score=score,
        constraints_restored=constraints_restored,
        constraints_required=constraints_required,
        decision=decision,
    )


def _states(pattern: str) -> list[str]:
    return [state for state in pattern.split("-") if state]
