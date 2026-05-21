from dataclasses import dataclass, field
from enum import StrEnum

from ai_local.planner.models import PlanItem


class AgentRunStatus(StrEnum):
    PENDING = "pending"
    PLANNED = "planned"
    WAITING_USER = "waiting_user"
    STOPPED = "stopped"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentRun:
    id: str
    goal: str
    project_id: str | None = None
    status: AgentRunStatus = AgentRunStatus.PENDING
    plan: list[PlanItem] = field(default_factory=list)
    decision: str | None = None
    next_state: str | None = None
