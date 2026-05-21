from dataclasses import dataclass

from ai_local.planner.models import PlanGateSignals, PlanItem


@dataclass(frozen=True)
class PlanGateDecision:
    decision: str
    next_state: str
    reason: str


def decide_plan(plan: list[PlanItem], signals: PlanGateSignals | None = None) -> PlanGateDecision:
    current_signals = signals or PlanGateSignals()
    if current_signals.unsafe or any(item.risk_level == "unsafe" for item in plan):
        return PlanGateDecision(
            decision="stop",
            next_state="STOP",
            reason="plan is unsafe",
        )
    if current_signals.ambiguity or not plan:
        return PlanGateDecision(
            decision="ask_user",
            next_state="ASK_USER",
            reason="plan needs clarification",
        )
    return PlanGateDecision(
        decision="continue",
        next_state="RETRIEVE",
        reason="plan accepted",
    )
