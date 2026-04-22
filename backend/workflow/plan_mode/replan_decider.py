"""Replan decision stub for future plan recovery."""

from __future__ import annotations

from workflow.plan_mode.plan_schema import PlanStep, StepResult
from workflow.state import CopilotState


def should_replan_after_step_failure(step: PlanStep, result: StepResult, state: CopilotState) -> bool:
    """Return whether executor should trigger replan.

    Automatic replan is intentionally disabled in this phase.
    """
    del step, result, state
    return False
