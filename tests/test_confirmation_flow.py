from ai_local.confirmation.manager import (
    confirmation_decision,
    request_evaluation_confirmation,
    request_confirmation,
    resolve_confirmation,
)
from ai_local.confirmation.models import (
    ConfirmationOption,
    ConfirmationQuestion,
    ConfirmationRequest,
    ConfirmationResolution,
)
from ai_local.evaluator.models import EvaluationScore
from ai_local.evaluator.service import evaluate


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


def _score(**overrides: float) -> EvaluationScore:
    values = {
        "correctness": 1.0,
        "completeness": 1.0,
        "evidence_quality": 1.0,
        "requirement_match": 1.0,
        "test_status": 1.0,
        "ambiguity": 0.1,
        "risk": 0.1,
    }
    values.update(overrides)
    return EvaluationScore(**values)


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


def test_evaluation_confirmation_routes_ambiguity_and_risk() -> None:
    ambiguous = request_evaluation_confirmation(
        evaluate(_score(ambiguity=0.75), retry_count=0),
        question=_question(),
    )
    risky = request_evaluation_confirmation(
        evaluate(_score(correctness=0.5, completeness=0.5, risk=0.55), retry_count=2),
        question=_question(),
    )
    accepted = request_evaluation_confirmation(
        evaluate(_score(), retry_count=0),
        question=_question(),
    )

    assert isinstance(ambiguous, ConfirmationRequest)
    assert ambiguous.trigger == "ambiguous_requirement"
    assert isinstance(risky, ConfirmationRequest)
    assert confirmation_decision(risky).decision == "ask_tech_lead"
    assert accepted is None
