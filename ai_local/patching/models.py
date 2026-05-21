from dataclasses import dataclass, field


@dataclass(frozen=True)
class PatchHarnessSpec:
    requirement_id: str
    objective: str
    level: str
    allowed_files: list[str]
    forbidden_files: list[str] = field(default_factory=list)
    evidence: set[str] = field(default_factory=set)
    checks: set[str] = field(default_factory=set)
    rollback_plan: str | None = None


@dataclass(frozen=True)
class PatchChangeSummary:
    files_changed: list[str]
    changed_lines: int
    functions_changed: int
    new_dependencies: int = 0
    change_types: set[str] = field(default_factory=set)
    risk: float = 0.0
    approved: bool = False


@dataclass(frozen=True)
class PatchCheckResult:
    id: str
    passed: bool
    serious: bool = False
    evidence_ref: str | None = None


@dataclass(frozen=True)
class PatchAttempt:
    harness: PatchHarnessSpec
    summary: PatchChangeSummary
    context_ready: bool
    semantic_review_passed: bool
    checks: list[PatchCheckResult]
    more_patch_required: bool = False


@dataclass(frozen=True)
class PatchDecision:
    decision: str
    next_stage: str
    reasons: list[str]
