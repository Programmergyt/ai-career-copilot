"""Plan validation for serial Plan Mode execution."""

from __future__ import annotations

from collections import deque

from agents.registry import AgentRegistry
from workflow.plan_mode.plan_schema import Plan, PlanStep
from workflow.state import CopilotState


class PlanValidationError(ValueError):
    """Raised when a generated plan is invalid."""


_PRECONDITION_FIELD_MAP = {
    "job_exists": "job",
    "candidate_profile_exists": "candidate_profile",
    "resume_content_exists": "resume_content_json",
}


def _state_has_field(state: CopilotState, field_name: str) -> bool:
    value = getattr(state, field_name, None)
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, str):
        return value != ""
    return True


def available_fields_after_plan_prefix(state: CopilotState, steps: list[PlanStep], step_index: int) -> set[str]:
    """Return fields available before executing the step at step_index."""
    available = {
        field_name
        for field_name in (
            "job",
            "candidate_profile",
            "resume_content_json",
            "render_config",
            "resume_html",
            "gaps",
            "questions_to_ask",
            "interview_qa",
        )
        if _state_has_field(state, field_name)
    }
    for prior_step in steps[:step_index]:
        available.update(prior_step.writes)
    return available


def check_step_preconditions(step: PlanStep, available_fields: set[str]) -> list[str]:
    """Return unsatisfied precondition kinds for a step."""
    unsatisfied: list[str] = []
    for precondition in step.preconditions:
        required_field = _PRECONDITION_FIELD_MAP[precondition.kind]
        if required_field not in available_fields:
            unsatisfied.append(precondition.kind)
    return unsatisfied


def _ensure_dependency_graph_is_valid(steps: list[PlanStep]) -> None:
    step_ids = [step.step_id for step in steps]
    if len(step_ids) != len(set(step_ids)):
        raise PlanValidationError("Plan contains duplicate step_id values")

    step_id_set = set(step_ids)
    indegree = {step.step_id: 0 for step in steps}
    edges: dict[str, list[str]] = {step.step_id: [] for step in steps}

    for step in steps:
        for dep_id in step.depends_on:
            if dep_id not in step_id_set:
                raise PlanValidationError(f"Step {step.step_id} depends on unknown step {dep_id}")
            edges[dep_id].append(step.step_id)
            indegree[step.step_id] += 1

    queue = deque([step_id for step_id, degree in indegree.items() if degree == 0])
    visited = 0
    while queue:
        node = queue.popleft()
        visited += 1
        for neighbor in edges[node]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(steps):
        raise PlanValidationError("Plan dependency graph contains a cycle")


def validate_plan(plan: Plan, state: CopilotState, registry: AgentRegistry) -> None:
    """Validate a plan against registry contracts and current state."""
    _ensure_dependency_graph_is_valid(plan.steps)

    for index, step in enumerate(plan.steps):
        if not registry.has(step.agent):
            raise PlanValidationError(f"Unknown agent in step {step.step_id}: {step.agent}")

        contract = registry.get_contract(step.agent)
        if step.intent not in contract.supported_intents:
            raise PlanValidationError(
                f"Agent {step.agent} does not support intent {step.intent} in step {step.step_id}"
            )
        if contract.supported_actions and step.action not in contract.supported_actions:
            raise PlanValidationError(
                f"Agent {step.agent} does not support action {step.action} in step {step.step_id}"
            )

        invalid_reads = sorted(set(step.reads) - set(contract.allowed_reads))
        if invalid_reads:
            raise PlanValidationError(
                f"Step {step.step_id} reads fields outside contract: {', '.join(invalid_reads)}"
            )

        invalid_writes = sorted(set(step.writes) - set(contract.allowed_writes))
        if invalid_writes:
            raise PlanValidationError(
                f"Step {step.step_id} writes fields outside contract: {', '.join(invalid_writes)}"
            )

        available_fields = available_fields_after_plan_prefix(state, plan.steps, index)
        unsatisfied = check_step_preconditions(step, available_fields)
        if unsatisfied:
            raise PlanValidationError(
                f"Step {step.step_id} has unsatisfied preconditions: {', '.join(unsatisfied)}"
            )
