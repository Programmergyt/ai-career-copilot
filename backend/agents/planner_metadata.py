"""Planner metadata helpers for legacy execution plans and step mirrors."""

from __future__ import annotations

import uuid

from agents.contracts import get_agent_contract
from workflow.state import CopilotState, ExecutionStep


_INTENT_PLAN: dict[str, list[str]] = {
    "upload_jd": ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"],
    "upload_profile": ["profile_agent", "content_agent", "render_agent", "interview_agent"],
    "content_edit": ["content_agent", "render_agent"],
    "render_edit": ["render_agent"],
    "export": [],
    "ask_question": ["gap_agent"],
}


def build_execution_plan(intent: str, state: CopilotState) -> list[str]:
    """Build the current legacy execution plan used by the workflow graph."""
    base_plan = _INTENT_PLAN.get(intent, [])

    if intent == "upload_jd" and state.candidate_profile is None:
        return ["jd_agent"]

    return list(base_plan)


def build_execution_steps(plan: list[str], *, plan_id: str) -> list[ExecutionStep]:
    """Build structured step metadata as a mirror of the current execution plan."""
    steps: list[ExecutionStep] = []
    for index, agent_name in enumerate(plan, start=1):
        contract = get_agent_contract(agent_name)
        steps.append(ExecutionStep(
            step_id=f"{plan_id}_st_{index:02d}",
            agent=agent_name,
            status="planned",
            reads=sorted(contract.allowed_reads),
            writes=sorted(contract.allowed_writes),
        ))
    return steps


def build_plan_metadata(intent: str, state: CopilotState) -> tuple[str, list[str], list[ExecutionStep]]:
    """Build the runtime plan id, legacy execution plan, and structured step metadata."""
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"
    plan = build_execution_plan(intent, state)
    steps = build_execution_steps(plan, plan_id=plan_id)
    return plan_id, plan, steps
