from dataclasses import dataclass, field
from typing import Literal

from ai_local.agent.loop import AgentLoop, AgentLoopResult, AgentSkillRuntimeResult
from ai_local.harness.patch_levels import PatchLevel
from ai_local.patching.models import (
    PatchAttempt,
    PatchChangeSummary,
    PatchCheckResult,
    PatchDecision,
    PatchEvidenceRef,
    PatchHarnessSpec,
)
from ai_local.patching.pipeline import POST_APPLY_STAGES, PRE_APPLY_STAGES, decide_patch_attempt
from ai_local.planner.models import PlanGateSignals
from ai_local.retrieval.models import ContextPackage
from ai_local.skills.models import SkillScriptRunRequest


PipelineStatus = Literal[
    "done",
    "needs_context",
    "needs_confirmation",
    "retry",
    "replan",
    "rollback",
    "quarantine",
    "stopped",
    "split",
]


@dataclass(frozen=True)
class IntegratedPipelineRequest:
    task_id: str
    goal: str
    skill_request: SkillScriptRunRequest | None = None
    patch_level: PatchLevel | None = None
    patch_attempt: PatchAttempt | None = None
    plan_signals: PlanGateSignals | None = None
    retry_count: int = 0
    hop_depth: int = 1
    noise_profile: str = "none"
    conflict_profile: str = "none"
    completion_ready: bool = True
    required_evidence: set[str] = field(default_factory=lambda: {"context", "test"})
    required_checks: set[str] = field(default_factory=lambda: {"test.integration"})
    max_retries_per_patch: int = 2


@dataclass(frozen=True)
class IntegratedPipelineResult:
    status: PipelineStatus
    final_state: str
    stages: list[str]
    evidence_refs: list[str]
    risk_flags: list[str]
    reasons: list[str]
    hop_depth: int
    noise_profile: str
    conflict_profile: str
    plan: AgentLoopResult
    skill: AgentSkillRuntimeResult | None = None
    patch: PatchDecision | None = None

    @property
    def output_ready(self) -> bool:
        return self.status == "done" and bool(self.evidence_refs)


class IntegratedDeveloperPipeline:
    def __init__(self, agent_loop: AgentLoop) -> None:
        self._agent_loop = agent_loop

    def run(self, request: IntegratedPipelineRequest) -> IntegratedPipelineResult:
        stages = ["TASK_INTAKE"]
        reasons: list[str] = []
        risk_flags: list[str] = []

        plan = self._agent_loop.run_once(
            request.task_id,
            request.goal,
            request.plan_signals,
        )
        stages.extend(["PLAN_GATE"])
        context = plan.context
        evidence_refs = _context_refs(context)

        if plan.decision.decision == "ask_user":
            return _result(
                request,
                plan,
                "needs_confirmation",
                "ASK_USER",
                stages,
                evidence_refs,
                risk_flags,
                [plan.decision.reason],
            )
        if plan.decision.decision == "stop":
            return _result(
                request,
                plan,
                "stopped",
                "STOP",
                stages,
                evidence_refs,
                risk_flags,
                [plan.decision.reason],
            )

        if context is not None:
            stages.extend(["RETRIEVE_CONTEXT", "CONTEXT_GATE"])
            reasons.append(context.reason)
            risk_flags.extend(_retrieval_flags(context))
            if context.decision == "quarantine":
                return _result(
                    request,
                    plan,
                    "quarantine",
                    "QUARANTINE",
                    stages,
                    evidence_refs,
                    risk_flags,
                    reasons,
                )
            if context.decision == "stop":
                return _result(
                    request,
                    plan,
                    "rollback",
                    "ROLLBACK",
                    stages,
                    evidence_refs,
                    risk_flags,
                    reasons,
                )

        skill = None
        if request.skill_request is not None:
            stages.extend(["TOOL_REGISTRY", "SKILL_RUNTIME", "EVIDENCE_RANK"])
            skill = self._agent_loop.execute_skill_runtime(
                request.skill_request,
                retry_count=request.retry_count,
                task_id=request.task_id,
                completion_ready=request.completion_ready,
            )
            evidence_refs.extend(skill.handoff.envelope.evidence_refs)
            risk_flags.extend(skill.handoff.envelope.risk_flags)
            reasons.append(skill.handoff.reason)
            if skill.route.next_state in {"ASK_USER", "QUARANTINE", "ROLLBACK"}:
                return _result(
                    request,
                    plan,
                    _status_from_state(skill.route.next_state),
                    skill.route.next_state,
                    stages,
                    evidence_refs,
                    risk_flags,
                    reasons,
                    skill=skill,
                )

        patch_decision = None
        if request.patch_level is not None:
            stages.extend(["PATCH_PIPELINE"])
            attempt = request.patch_attempt or _default_patch_attempt(
                request,
                context=context,
                skill=skill,
            )
            patch_decision = decide_patch_attempt(
                attempt,
                request.patch_level,
                required_evidence=request.required_evidence,
                required_checks=request.required_checks,
                max_retries_per_patch=request.max_retries_per_patch,
            )
            stages.append(patch_decision.next_stage)
            reasons.extend(patch_decision.reasons)
            return _result(
                request,
                plan,
                _status_from_patch(patch_decision),
                patch_decision.next_stage,
                stages,
                evidence_refs,
                risk_flags,
                reasons,
                skill=skill,
                patch=patch_decision,
            )

        return _result(
            request,
            plan,
            _status_from_state(skill.route.next_state if skill is not None else "DONE"),
            skill.route.next_state if skill is not None else "DONE",
            stages,
            evidence_refs,
            risk_flags,
            reasons,
            skill=skill,
        )


def _default_patch_attempt(
    request: IntegratedPipelineRequest,
    *,
    context: ContextPackage | None,
    skill: AgentSkillRuntimeResult | None,
) -> PatchAttempt:
    context_refs = _context_refs(context)
    skill_succeeded = skill is not None and skill.script_result.decision == "succeeded"
    no_path_conflict = request.conflict_profile == "no_path"
    multi_conflict = request.conflict_profile in {"forced_choice", "multi_instance"}
    serious_failure = no_path_conflict or any(
        flag in {"prompt_injection", "deep_policy_shadowing", "deep_chain_interference"}
        for flag in _retrieval_flags(context)
    )
    passed_check = skill_succeeded and not serious_failure
    risk = 0.65 if multi_conflict else 0.25
    if request.hop_depth > 25:
        risk = max(risk, 0.70)

    return PatchAttempt(
        harness=PatchHarnessSpec(
            requirement_id=request.task_id,
            objective=request.goal,
            level=request.patch_level.name if request.patch_level is not None else "medium",
            allowed_files=[
                "ai_local/pipeline/integration.py",
                "tests/test_integration_pipeline.py",
            ],
            evidence={"context", "test"},
            evidence_refs=[
                *(PatchEvidenceRef("context", ref) for ref in context_refs),
                PatchEvidenceRef("test", "pytest:tests/test_integration_pipeline.py"),
            ],
            checks={"test.integration"},
            rollback_plan="revert integration patch and keep evidence audit",
        ),
        summary=PatchChangeSummary(
            files_changed=["ai_local/pipeline/integration.py", "tests/test_integration_pipeline.py"],
            changed_lines=90,
            functions_changed=4,
            change_types={"multi_module_feature"},
            risk=risk,
            approved=request.patch_level.requires_confirmation
            if request.patch_level is not None
            else False,
        ),
        context_ready=bool(context_refs) and context is not None and context.decision == "continue",
        semantic_review_passed=not no_path_conflict,
        checks=[
            PatchCheckResult(
                id="test.integration",
                passed=passed_check,
                serious=serious_failure,
                evidence_ref=PatchEvidenceRef("test", "pytest:tests/test_integration_pipeline.py"),
            )
        ],
        completed_stages=[*PRE_APPLY_STAGES, *POST_APPLY_STAGES],
        evaluator_passed=passed_check,
        evaluator_evidence_ref=PatchEvidenceRef("test", "pytest:integration-output"),
        retry_count=request.retry_count,
    )


def _context_refs(context: ContextPackage | None) -> list[str]:
    return context.evidence_refs if context is not None else []


def _retrieval_flags(context: ContextPackage | None) -> list[str]:
    if context is None:
        return []
    return [flag for hit in [*context.selected_hits, *context.rejected_hits] for flag in hit.flags]


def _status_from_patch(decision: PatchDecision) -> PipelineStatus:
    mapping: dict[str, PipelineStatus] = {
        "accept": "done",
        "finish": "done",
        "retrieve_more": "needs_context",
        "ask_user": "needs_confirmation",
        "retry": "retry",
        "rollback": "rollback",
        "split": "split",
        "next_patch": "retry",
        "quarantine": "quarantine",
        "stop": "stopped",
    }
    return mapping.get(decision.decision, "retry")


def _status_from_state(next_state: str) -> PipelineStatus:
    mapping: dict[str, PipelineStatus] = {
        "DONE": "done",
        "DECISION_GATE": "done",
        "VERIFY_EVIDENCE": "needs_context",
        "ASK_USER": "needs_confirmation",
        "MODEL_PROPOSE_PATCH": "retry",
        "PLAN": "replan",
        "ROLLBACK": "rollback",
        "QUARANTINE": "quarantine",
        "STOP": "stopped",
    }
    return mapping.get(next_state, "retry")


def _result(
    request: IntegratedPipelineRequest,
    plan: AgentLoopResult,
    status: PipelineStatus,
    final_state: str,
    stages: list[str],
    evidence_refs: list[str],
    risk_flags: list[str],
    reasons: list[str],
    *,
    skill: AgentSkillRuntimeResult | None = None,
    patch: PatchDecision | None = None,
) -> IntegratedPipelineResult:
    return IntegratedPipelineResult(
        status=status,
        final_state=final_state,
        stages=stages,
        evidence_refs=_unique(evidence_refs),
        risk_flags=_unique(risk_flags),
        reasons=[reason for reason in reasons if reason],
        hop_depth=request.hop_depth,
        noise_profile=request.noise_profile,
        conflict_profile=request.conflict_profile,
        plan=plan,
        skill=skill,
        patch=patch,
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
