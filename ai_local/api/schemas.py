from pydantic import BaseModel, Field

from ai_local.planner.models import PlanItem


class TaskCreate(BaseModel):
    goal: str = Field(min_length=1)
    project_id: str | None = None


class TaskCreated(BaseModel):
    task_id: str
    status: str


class TaskState(BaseModel):
    task_id: str
    goal: str
    project_id: str | None = None
    status: str
    decision: str | None = None
    next_state: str | None = None
    plan: list[PlanItem] = Field(default_factory=list)
