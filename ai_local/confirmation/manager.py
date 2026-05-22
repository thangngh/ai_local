from ai_local.confirmation.models import (
    ConfirmationNoise,
    ConfirmationQuestion,
    ConfirmationRequest,
    ConfirmationResolution,
    ConfirmationTrigger,
)
from ai_local.evaluator.models import EvaluationResult


def request_confirmation(
    *,
    trigger: ConfirmationTrigger,
    question: ConfirmationQuestion,
    noise_type: ConfirmationNoise = "none",
) -> ConfirmationResolution | ConfirmationRequest:
    if noise_type == "fake_approval_laundering":
        return ConfirmationResolution(
            decision="stop",
            next_state="STOP",
            reason="retrieved or laundered approval is invalid",
        )
    if noise_type == "prompt_injected_options":
        return ConfirmationResolution(
            decision="quarantine",
            next_state="QUARANTINE",
            reason="confirmation options contain untrusted instructions",
        )
    if trigger == "technical_risk":
        return ConfirmationRequest(trigger=trigger, question=question, audience="tech_lead")
    if trigger == "dangerous_action":
        return ConfirmationRequest(
            trigger=trigger,
            question=question,
            requires_current_user_approval=True,
            noise_type=noise_type,
        )
    return ConfirmationRequest(trigger=trigger, question=question, noise_type=noise_type)


def confirmation_decision(request: ConfirmationRequest) -> ConfirmationResolution:
    if request.trigger == "technical_risk":
        return ConfirmationResolution(
            decision="ask_tech_lead",
            next_state="WAIT_FOR_TECH_LEAD",
            reason="technical risk needs lead confirmation",
        )
    if request.trigger == "dangerous_action":
        return ConfirmationResolution(
            decision="require_approval",
            next_state="WAIT_FOR_HUMAN",
            reason="dangerous action requires current user approval",
        )
    if request.trigger == "ambiguous_requirement":
        return ConfirmationResolution(
            decision="wait_for_user",
            next_state="WAIT_FOR_HUMAN",
            reason="structured options are ready for user selection",
        )
    return ConfirmationResolution(
        decision="ask_user",
        next_state="WAIT_FOR_HUMAN",
        reason="confirmation is required before the run continues",
    )


def resolve_confirmation(
    *,
    trigger: ConfirmationTrigger,
    approved_by_current_user: bool = False,
) -> ConfirmationResolution:
    if trigger == "conflicting_answer":
        return ConfirmationResolution(
            decision="ask_user",
            next_state="WAIT_FOR_HUMAN",
            reason="confirmation conflicts with current context",
        )
    if trigger == "confirmed_policy":
        return ConfirmationResolution(
            decision="save_policy_and_resume",
            next_state="RESUME_AGENT_RUN",
            reason="confirmed policy is durable decision knowledge",
            save_as="K6_DECISION_POLICY",
        )
    if trigger == "user_confirmed_fact":
        return ConfirmationResolution(
            decision="save_fact_and_resume",
            next_state="RESUME_AGENT_RUN",
            reason="confirmed user fact can ground the run",
            save_as="K5_GROUND_TRUTH",
        )
    if trigger == "safety_policy":
        return ConfirmationResolution(
            decision="save_policy_not_preference",
            next_state="RESUME_AGENT_RUN",
            reason="safety policy must not become a preference",
            save_as="K6_DECISION_POLICY",
        )
    if trigger == "dangerous_action" and not approved_by_current_user:
        return ConfirmationResolution(
            decision="require_approval",
            next_state="WAIT_FOR_HUMAN",
            reason="dangerous action still lacks current user approval",
        )
    return ConfirmationResolution(
        decision="wait_for_user",
        next_state="RESUME_AGENT_RUN" if approved_by_current_user else "WAIT_FOR_HUMAN",
        reason="confirmation response processed",
    )


def request_evaluation_confirmation(
    result: EvaluationResult,
    *,
    question: ConfirmationQuestion,
) -> ConfirmationResolution | ConfirmationRequest | None:
    if result.decision != "ask_user":
        return None
    trigger: ConfirmationTrigger = (
        "technical_risk" if result.score.risk >= 0.50 else "ambiguous_requirement"
    )
    return request_confirmation(trigger=trigger, question=question)
