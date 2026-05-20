from ai_local.planner.models import PlanItem


def plan_from_goal(goal: str) -> list[PlanItem]:
    return [PlanItem(intent=f"Analyze requirement: {goal}", required_tools=["requirements.extract"])]

