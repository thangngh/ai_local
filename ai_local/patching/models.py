from dataclasses import dataclass, field
from typing import Literal


PatchEvidenceKind = Literal["context", "diff", "test", "manual"]


@dataclass(frozen=True)
class PatchEvidenceRef:
    kind: PatchEvidenceKind
    ref: str


@dataclass(frozen=True)
class PatchHarnessSpec:
    requirement_id: str
    objective: str
    level: str
    allowed_files: list[str]
    forbidden_files: list[str] = field(default_factory=list)
    evidence: set[str] = field(default_factory=set)
    evidence_refs: list[PatchEvidenceRef] = field(default_factory=list)
    checks: set[str] = field(default_factory=set)
    rollback_plan: str | None = None


@dataclass(frozen=True)
class PatchFileChange:
    path: str
    added_lines: int
    removed_lines: int
    functions_changed: int = 0
    change_types: set[str] = field(default_factory=set)

    @property
    def changed_lines(self) -> int:
        return self.added_lines + self.removed_lines


@dataclass(frozen=True)
class PatchChangeSummary:
    files_changed: list[str]
    changed_lines: int
    functions_changed: int
    new_dependencies: int = 0
    change_types: set[str] = field(default_factory=set)
    risk: float = 0.0
    approved: bool = False

    @classmethod
    def from_diff(
        cls,
        changes: list[PatchFileChange],
        *,
        new_dependencies: int = 0,
        risk: float = 0.0,
        approved: bool = False,
    ) -> "PatchChangeSummary":
        return cls(
            files_changed=[change.path for change in changes],
            changed_lines=sum(change.changed_lines for change in changes),
            functions_changed=sum(change.functions_changed for change in changes),
            new_dependencies=new_dependencies,
            change_types={item for change in changes for item in change.change_types},
            risk=risk,
            approved=approved,
        )


@dataclass(frozen=True)
class PatchCheckResult:
    id: str
    passed: bool
    serious: bool = False
    evidence_ref: PatchEvidenceRef | None = None


@dataclass(frozen=True)
class PatchAttempt:
    harness: PatchHarnessSpec
    summary: PatchChangeSummary
    context_ready: bool
    semantic_review_passed: bool
    checks: list[PatchCheckResult]
    completed_stages: list[str] = field(default_factory=list)
    evaluator_passed: bool = True
    evaluator_evidence_ref: PatchEvidenceRef | None = None
    more_patch_required: bool = False


@dataclass(frozen=True)
class PatchDecision:
    decision: str
    next_stage: str
    reasons: list[str]
