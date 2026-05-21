from dataclasses import dataclass

from ai_local.memory.models import MemoryLevel, MemoryScope


@dataclass(frozen=True)
class MemoryLayerPolicy:
    level: MemoryLevel
    scopes: frozenset[MemoryScope]
    may_be_policy: bool
    inject_as_fact: bool
    min_evidence_strength: float = 0.0
    requires_confirmation: bool = False


MEMORY_LAYER_POLICIES: dict[MemoryLevel, MemoryLayerPolicy] = {
    "M0_SESSION_SCRATCH": MemoryLayerPolicy(
        level="M0_SESSION_SCRATCH",
        scopes=frozenset({"session"}),
        may_be_policy=False,
        inject_as_fact=False,
    ),
    "M1_PERSONAL_PREFERENCE": MemoryLayerPolicy(
        level="M1_PERSONAL_PREFERENCE",
        scopes=frozenset({"global", "project"}),
        may_be_policy=False,
        inject_as_fact=False,
    ),
    "M2_PROJECT_CONVENTION": MemoryLayerPolicy(
        level="M2_PROJECT_CONVENTION",
        scopes=frozenset({"project", "repo"}),
        may_be_policy=False,
        inject_as_fact=True,
        min_evidence_strength=0.60,
    ),
    "M3_CONFIRMED_DECISION": MemoryLayerPolicy(
        level="M3_CONFIRMED_DECISION",
        scopes=frozenset({"global", "project", "repo"}),
        may_be_policy=True,
        inject_as_fact=True,
        min_evidence_strength=0.80,
        requires_confirmation=True,
    ),
    "M4_WORKFLOW_MEMORY": MemoryLayerPolicy(
        level="M4_WORKFLOW_MEMORY",
        scopes=frozenset({"global", "project", "repo"}),
        may_be_policy=False,
        inject_as_fact=True,
    ),
    "M5_SAFETY_POLICY": MemoryLayerPolicy(
        level="M5_SAFETY_POLICY",
        scopes=frozenset({"global", "project", "repo"}),
        may_be_policy=True,
        inject_as_fact=True,
        requires_confirmation=True,
    ),
}
