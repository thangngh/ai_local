from ai_local.confirmation.manager import (
    confirmation_decision,
    request_confirmation,
    resolve_confirmation,
)
from ai_local.confirmation.models import (
    ConfirmationOption,
    ConfirmationQuestion,
    ConfirmationRequest,
    ConfirmationResolution,
)


def _question() -> ConfirmationQuestion:
    return ConfirmationQuestion(
        ambiguity_or_risk_summary="Deleting the old index may remove active records.",
        options=[
            ConfirmationOption(label="Delete", impact="Rebuild all index rows."),
            ConfirmationOption(label="Keep", impact="Preserve current rows."),
        ],
        recommendation="Keep until audit evidence is complete.",
        evidence=["patch risk score is high", "outbox action is destructive"],
    )


def test_confirmation_request_routes_technical_risk_and_destructive_action() -> None:
    technical = request_confirmation(trigger="technical_risk", question=_question())
    destructive = request_confirmation(trigger="dangerous_action", question=_question())

    assert isinstance(technical, ConfirmationRequest)
    assert confirmation_decision(technical).decision == "ask_tech_lead"
    assert isinstance(destructive, ConfirmationRequest)
    assert destructive.requires_current_user_approval
    assert confirmation_decision(destructive).decision == "require_approval"


def test_confirmation_blocks_laundered_or_injected_confirmation() -> None:
    fake_approval = request_confirmation(
        trigger="dangerous_action",
        question=_question(),
        noise_type="fake_approval_laundering",
    )
    injected_options = request_confirmation(
        trigger="business_ambiguity",
        question=_question(),
        noise_type="prompt_injected_options",
    )

    assert isinstance(fake_approval, ConfirmationResolution)
    assert isinstance(injected_options, ConfirmationResolution)
    assert fake_approval.decision == "stop"
    assert injected_options.decision == "quarantine"


def test_confirmation_resolution_saves_policy_and_fact_at_right_levels() -> None:
    policy = resolve_confirmation(trigger="confirmed_policy")
    fact = resolve_confirmation(trigger="user_confirmed_fact")
    safety = resolve_confirmation(trigger="safety_policy")

    assert (policy.decision, policy.save_as, policy.next_state) == (
        "save_policy_and_resume",
        "K6_DECISION_POLICY",
        "RESUME_AGENT_RUN",
    )
    assert (fact.decision, fact.save_as) == ("save_fact_and_resume", "K5_GROUND_TRUTH")
    assert (safety.decision, safety.save_as) == (
        "save_policy_not_preference",
        "K6_DECISION_POLICY",
    )


def test_conflicting_confirmation_asks_again_and_dangerous_action_waits_for_approval() -> None:
    assert resolve_confirmation(trigger="conflicting_answer").decision == "ask_user"
    assert resolve_confirmation(trigger="dangerous_action").decision == "require_approval"
    assert resolve_confirmation(
        trigger="dangerous_action",
        approved_by_current_user=True,
    ).next_state == "RESUME_AGENT_RUN"
