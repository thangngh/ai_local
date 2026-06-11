"""Planner service.

Provides multi-step plan generation:
- Deterministic stub for offline/testing
- OllamaPlanner for LLM-generated plans
"""
from __future__ import annotations

import json
from typing import Any

from ai_local.llm.ollama import OllamaClient, OllamaError
from ai_local.planner.models import PlanItem


def plan_from_goal(
    goal: str,
    ollama_client: OllamaClient | None = None,
    known_files: list[str] | None = None,
) -> list[PlanItem]:
    """Generate a plan for the given goal.

    Uses Ollama when available, otherwise falls back to deterministic stub.
    """
    if ollama_client is not None:
        try:
            planner = OllamaPlanner(ollama_client)
            return planner.plan(goal, known_files=known_files or [])
        except OllamaError:
            return _deterministic_plan(goal, known_files=known_files or [])
    return _deterministic_plan(goal, known_files=known_files or [])


def _deterministic_plan(goal: str, known_files: list[str] | None = None) -> list[PlanItem]:
    """Deterministic stub that produces a single generic plan item."""
    _ = known_files  # unused in stub
    return [
        PlanItem(
            intent=f"Analyze requirement: {goal}",
            required_tools=["requirements.extract"],
        )
    ]


class OllamaPlanner:
    """LLM-based planner using Ollama chat."""

    def __init__(
        self,
        client: OllamaClient,
        model: str | None = None,
    ) -> None:
        self._client = client
        self._model = model

    def plan(
        self,
        goal: str,
        known_files: list[str] | None = None,
    ) -> list[PlanItem]:
        """Generate a multi-step plan from the goal."""
        system = (
            "You are a senior software engineer planning code changes. "
            "Given a goal and context, produce a JSON array of plan steps. "
            "Each step must have keys: "
            '"step" (int), "action" (str), "detail" (str), '
            '"tools" (list of str), "risk" ("low"|"medium"|"high"|"unsafe"). '
            "Tools available: search_knowledge, search_index, read_file, write_file, list_files. "
            "Return ONLY valid JSON, no markdown, no explanation."
        )
        files_context = ""
        if known_files:
            files_context = "\nKnown files:\n" + "\n".join(f"- {f}" for f in known_files[:20])

        user = json.dumps({
            "goal": goal,
            "known_files": (known_files or [])[:20],
        })

        result = self._client.chat(
            system=system,
            user=user,
            model=self._model,
        )
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]

        steps: list[dict[str, Any]] = json.loads(raw)
        if not isinstance(steps, list):
            raise ValueError("LLM did not return a list")

        plan_items: list[PlanItem] = []
        for step in steps:
            risk = step.get("risk", "low")
            tools = step.get("tools", [])

            plan_items.append(PlanItem(
                intent=f"Step {step.get('step', len(plan_items) + 1)}: {step.get('action', '')}: {step.get('detail', '')}",
                required_tools=tools if isinstance(tools, list) else [tools],
                risk_level=risk if risk in ("low", "medium", "high", "unsafe") else "low",
            ))

        if not plan_items:
            return _deterministic_plan(goal)
        return plan_items
