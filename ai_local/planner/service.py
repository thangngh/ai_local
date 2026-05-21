from ai_local.planner.models import PlanItem


def plan_from_goal(goal: str) -> list[PlanItem]:
    normalized_goal = goal.strip()
    return [
        PlanItem(
            intent=f"Analyze requirement: {normalized_goal}",
            required_tools=["requirements.extract"],
        )
    ]
