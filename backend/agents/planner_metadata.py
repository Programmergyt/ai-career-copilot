"""Compatibility helpers around the dynamic plan builder."""

from __future__ import annotations

from workflow.plan_mode.plan_builder import build_plan_from_tasks
from workflow.state import CopilotState


def build_plan(intent: str, state: CopilotState):
    """Build a plan for a single legacy intent."""
    return build_plan_from_tasks([intent], state, primary_intent=intent)


def build_plan_metadata(intent: str, state: CopilotState):
    """Build a plan plus the legacy execution_plan mirror."""
    plan = build_plan(intent, state)
    execution_plan = [step.agent for step in plan.steps]
    return plan, execution_plan
