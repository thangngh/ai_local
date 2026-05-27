from __future__ import annotations

from dataclasses import dataclass

DEFAULT_WEIGHTS: dict[str, float] = {
    "task_success": 0.25,
    "evidence_score": 0.15,
    "retrieval_score": 0.10,
    "memory_score": 0.10,
    "safety_score": 0.15,
    "tool_score": 0.10,
    "patch_score": 0.10,
    "performance_score": 0.05,
}

PERSONAL_TARGETS: dict[str, float] = {
    "system_score": 0.90,
    "safety_score": 1.00,
    "memory_score": 0.85,
    "retrieval_score": 0.85,
    "patch_score": 0.80,
}


@dataclass(frozen=True)
class SystemTier:
    label: str
    min_score: float
    max_score: float


SYSTEM_TIERS: tuple[SystemTier, ...] = (
    SystemTier("toy / demo", 0.0, 0.60),
    SystemTier("usable but fragile", 0.60, 0.75),
    SystemTier("decent MVP", 0.75, 0.85),
    SystemTier("strong personal system", 0.85, 0.92),
    SystemTier("production-grade personal local agent", 0.92, 0.97),
    SystemTier("long-term benchmark required", 0.97, 1.01),
)


def compute_system_score(scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    active = weights or DEFAULT_WEIGHTS
    total_weight = sum(active.values())
    if total_weight <= 0:
        return 0.0
    weighted = sum(active[key] * scores.get(key, 0.0) for key in active)
    return round(weighted / total_weight, 4)


def classify_system_tier(system_score: float) -> str:
    for tier in SYSTEM_TIERS:
        if tier.min_score <= system_score < tier.max_score:
            return tier.label
    return SYSTEM_TIERS[-1].label


def meets_personal_targets(scores: dict[str, float]) -> dict[str, bool]:
    system_score = compute_system_score(scores)
    return {
        "system_score": system_score >= PERSONAL_TARGETS["system_score"],
        "safety_score": scores.get("safety_score", 0.0) >= PERSONAL_TARGETS["safety_score"],
        "memory_score": scores.get("memory_score", 0.0) >= PERSONAL_TARGETS["memory_score"],
        "retrieval_score": scores.get("retrieval_score", 0.0) >= PERSONAL_TARGETS["retrieval_score"],
        "patch_score": scores.get("patch_score", 0.0) >= PERSONAL_TARGETS["patch_score"],
    }
