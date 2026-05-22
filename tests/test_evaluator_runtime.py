from ai_local.audit.store import InMemoryAuditStore
from ai_local.evaluator.models import EvaluationScore
from ai_local.confirmation.manager import resolve_confirmation
from ai_local.evaluator.models import EvaluationEvidence, ObservationEvaluationInput
from ai_local.evaluator.service import (
    evaluate,
    evaluate_observation,
    re_evaluate_after_confirmation,
    re_evaluate_with_context,
    route_evaluation,
)
from ai_local.indexer.models import IndexedChunk
from ai_local.retrieval.retriever import retrieve_chunks


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


def test_evaluator_returns_score_reason_and_accept_decision() -> None:
    result = evaluate(_score(), retry_count=0)

    assert result.decision == "accept"
    assert result.final_score == result.score.final_score
    assert result.reason == "score and risk thresholds passed"


def test_evaluator_verifies_weak_evidence_before_accepting_score() -> None:
    result = evaluate(_score(evidence_quality=0.2), retry_count=0)

    assert result.decision == "verify"
    assert result.reason == "evidence quality below floor"


def test_evaluator_security_signals_choose_protected_paths() -> None:
    assert evaluate(_score(), retry_count=0, security_signal="tool_policy_override").decision == (
        "quarantine"
    )
    assert evaluate(_score(), retry_count=0, security_signal="memory_conflict").decision == "verify"
    assert evaluate(_score(), retry_count=0, security_signal="deep_policy_shadowing").decision == (
        "stop"
    )


def test_evaluator_stops_retrying_after_budget() -> None:
    result = evaluate(_score(correctness=0.65, completeness=0.65), retry_count=2)

    assert result.decision == "ask_user"
    assert "retry budget exhausted" in result.reason


def test_evaluator_rechecks_verify_result_with_context_evidence() -> None:
    verify = evaluate(_score(evidence_quality=0.2), retry_count=0)
    context = retrieve_chunks(
        "evaluation evidence",
        [
            IndexedChunk(
                file_path="docs/eval.md",
                chunk_type="doc",
                start_line=4,
                end_line=6,
                content="evaluation evidence proves patch score",
                content_hash="eval",
                evidence_strength=0.9,
            )
        ],
    )

    result = re_evaluate_with_context(
        verify,
        context,
        test_refs=["pytest:tests/test_evaluator_runtime.py"],
    )

    assert result.decision == "accept"
    assert result.evidence.context_refs == ["docs/eval.md:4-6"]
    assert result.evidence.ready_for_accept


def test_evaluator_routes_accept_without_payload_to_verify_and_audits_security_exit() -> None:
    audit = InMemoryAuditStore()
    accept_without_evidence = route_evaluation(evaluate(_score(), retry_count=0))
    quarantine = route_evaluation(
        evaluate(_score(), retry_count=0, security_signal="tool_policy_override"),
        audit_store=audit,
    )
    stop = route_evaluation(evaluate(_score(risk=0.9), retry_count=0), audit_store=audit)

    assert accept_without_evidence.decision == "verify"
    assert accept_without_evidence.next_state == "VERIFY_EVIDENCE"
    assert quarantine.next_state == "QUARANTINE"
    assert stop.next_state == "ROLLBACK"
    assert [event.result for event in audit.list_events()] == ["quarantine", "stop"]


def test_evaluator_audits_verify_route_before_context_is_ready() -> None:
    audit = InMemoryAuditStore()

    route = route_evaluation(
        evaluate(_score(evidence_quality=0.2), retry_count=0),
        audit_store=audit,
    )

    assert route.next_state == "VERIFY_EVIDENCE"
    assert audit.list_events()[0].target == "VERIFY_EVIDENCE"


def test_evaluator_rechecks_ambiguity_after_confirmation_without_losing_evidence() -> None:
    result = re_evaluate_after_confirmation(
        evaluate(
            _score(ambiguity=0.75),
            retry_count=0,
            evidence=EvaluationEvidence(
                context_refs=["docs/confirmation.md:1-3"],
                test_refs=["pytest:tests/test_evaluator_runtime.py"],
            ),
        ),
        resolve_confirmation(trigger="confirmed_policy"),
    )

    assert result.decision == "accept"
    assert result.score.ambiguity == 0.39
    assert result.evidence.context_refs == ["docs/confirmation.md:1-3"]
    assert result.evidence.decision_refs == ["confirmation:save_policy_and_resume"]


def test_evaluator_observation_retries_failed_tool_then_replans_after_budget() -> None:
    observation = ObservationEvaluationInput(
        tool_name="shell.pytest",
        tool_status="failed",
        output_present=True,
    )

    retry = evaluate_observation(observation, retry_count=0)
    replan = evaluate_observation(observation, retry_count=2)

    assert retry.decision == "retry"
    assert route_evaluation(retry).next_state == "MODEL_PROPOSE_PATCH"
    assert replan.decision == "replan"
    assert route_evaluation(replan).next_state == "PLAN"


def test_evaluator_observation_verifies_empty_output_and_finishes_with_evidence() -> None:
    empty = evaluate_observation(
        ObservationEvaluationInput(
            tool_name="shell.rg_search",
            tool_status="succeeded",
            output_present=False,
        ),
        retry_count=0,
    )
    finished = evaluate_observation(
        ObservationEvaluationInput(
            tool_name="shell.pytest",
            tool_status="succeeded",
            output_present=True,
            completion_ready=True,
        ),
        retry_count=0,
        evidence=EvaluationEvidence(
            context_refs=["tool:shell.pytest"],
            test_refs=["pytest:tests/test_evaluator_runtime.py"],
        ),
    )

    assert empty.decision == "verify"
    assert route_evaluation(empty).next_state == "VERIFY_EVIDENCE"
    assert finished.decision == "finish"
    assert route_evaluation(finished).next_state == "DONE"
