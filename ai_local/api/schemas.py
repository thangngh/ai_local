from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    goal: str = Field(min_length=1)
    project_id: str | None = None


class TaskCreated(BaseModel):
    task_id: str
    status: str

