from typing import Literal

from pydantic import BaseModel, Field


ConfirmationAudience = Literal["user", "tech_lead"]
ConfirmationDecision = Literal[
    "ask_user",
    "ask_tech_lead",
    "require_approval",
    "wait_for_user",
    "save_policy_and_resume",
    "save_fact_and_resume",
    "save_policy_not_preference",
    "quarantine",
    "stop",
]
ConfirmationTrigger = Literal[
    "business_ambiguity",
    "ambiguous_requirement",
    "technical_risk",
    "dangerous_action",
    "conflicting_answer",
    "confirmed_policy",
    "user_confirmed_fact",
    "safety_policy",
]
ConfirmationNoise = Literal[
    "none",
    "mild_requirement_noise",
    "risk_label_noise",
    "command_noise",
    "conflicting_user_context",
    "stale_memory_interference",
    "preference_policy_confusion",
    "fake_approval_laundering",
    "prompt_injected_options",
]
KnowledgeSaveLevel = Literal["K5_GROUND_TRUTH", "K6_DECISION_POLICY"]


class ConfirmationOption(BaseModel):
    label: str = Field(min_length=1)
    impact: str = Field(min_length=1)


class ConfirmationQuestion(BaseModel):
    ambiguity_or_risk_summary: str = Field(min_length=1)
    options: list[ConfirmationOption] = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)


class ConfirmationRequest(BaseModel):
    trigger: ConfirmationTrigger
    question: ConfirmationQuestion
    audience: ConfirmationAudience = "user"
    requires_current_user_approval: bool = False
    noise_type: ConfirmationNoise = "none"


class ConfirmationResolution(BaseModel):
    decision: ConfirmationDecision
    next_state: str
    reason: str
    save_as: KnowledgeSaveLevel | None = None
