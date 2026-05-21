from dataclasses import dataclass

from ai_local.harness.patch_levels import PatchLevel
from ai_local.patching.models import PatchChangeSummary, PatchHarnessSpec


@dataclass(frozen=True)
class PatchPolicyResult:
    passed: bool
    decision: str
    reasons: list[str]


def validate_patch_harness(
    spec: PatchHarnessSpec,
    summary: PatchChangeSummary,
    level: PatchLevel,
    *,
    required_evidence: set[str],
    required_checks: set[str],
) -> PatchPolicyResult:
    reasons: list[str] = []
    if not spec.requirement_id:
        reasons.append("requirement_id missing")
    if not spec.allowed_files:
        reasons.append("allowed_files missing")
    if required_evidence - spec.evidence:
        reasons.append("required evidence missing")
    if required_checks - spec.checks:
        reasons.append("required checks missing")
    if any(path in spec.forbidden_files for path in summary.files_changed):
        reasons.append("forbidden file changed")
    if any(path not in spec.allowed_files for path in summary.files_changed):
        reasons.append("changed file outside scope")
    if summary.new_dependencies > level.max_new_dependencies:
        reasons.append("new dependency exceeds level")
    if summary.changed_lines > level.max_changed_lines:
        return PatchPolicyResult(False, "split", [*reasons, "changed lines exceed level"])
    if len(summary.files_changed) > level.max_files_changed:
        return PatchPolicyResult(False, "split", [*reasons, "changed files exceed level"])
    if summary.functions_changed > level.max_functions_changed:
        return PatchPolicyResult(False, "split", [*reasons, "changed functions exceed level"])
    if summary.risk > level.risk_ceiling and not summary.approved:
        return PatchPolicyResult(False, "ask_user", [*reasons, "risk exceeds level"])
    if level.requires_rollback_plan and not spec.rollback_plan:
        reasons.append("rollback plan missing")
    if reasons:
        return PatchPolicyResult(False, "reject", reasons)
    return PatchPolicyResult(True, "continue", [])
