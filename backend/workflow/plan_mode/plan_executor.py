"""Serial Plan Mode executor."""

from __future__ import annotations

from typing import Any

from agents.registry import get_default_registry
from agents.runtime import run_agent_async
from log import get_logger
from workflow.plan_mode.error_policy import classify_step_decision
from workflow.plan_mode.plan_schema import PlanStep, StepResult
from workflow.plan_mode.replan_decider import should_replan_after_step_failure
from workflow.plan_mode.plan_validator import check_step_preconditions, available_fields_after_plan_prefix
from workflow.state import CopilotState

logger = get_logger("agent")


def _copy_model(model: Any, **kwargs):
    if hasattr(model, "model_copy"):
        return model.model_copy(**kwargs)
    return model.copy(**kwargs)


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _set_step_status(steps: list[PlanStep], step_id: str, status: str) -> list[PlanStep]:
    updated: list[PlanStep] = []
    for step in steps:
        if step.step_id == step_id:
            updated.append(_copy_model(step, update={"status": status}))
        else:
            updated.append(step)
    return updated


def _append_step_result(state: CopilotState, result: StepResult) -> CopilotState:
    return _copy_model(state, update={"step_results": [*state.step_results, result]})


async def plan_executor_node_async(state: CopilotState) -> dict[str, Any]:
    """Execute the current plan serially and merge state after each step."""
    registry = get_default_registry()
    current_state = _copy_model(state, update={
        "plan_status": "running",
        "last_plan_error": "",
        "replan_candidate": False,
    })
    completed_with_degradation = False

    if not current_state.execution_steps:
        return {"plan_status": "success"}

    for index, step in enumerate(current_state.execution_steps):
        available_fields = available_fields_after_plan_prefix(current_state, current_state.execution_steps, index)
        unsatisfied = check_step_preconditions(step, available_fields)
        if unsatisfied:
            failed_steps = _set_step_status(current_state.execution_steps, step.step_id, "failed")
            current_state = _copy_model(current_state, update={
                "execution_steps": failed_steps,
                "plan_status": "failed",
                "last_plan_error": ",".join(unsatisfied),
                "replan_candidate": False,
                "reply_message": f"计划执行失败：步骤 {step.action} 缺少前置条件 {', '.join(unsatisfied)}。",
            })
            return _dump_model(current_state)

        running_steps = _set_step_status(current_state.execution_steps, step.step_id, "running")
        current_state = _copy_model(current_state, update={"execution_steps": running_steps})

        success = False
        for attempt in range(1, step.retry.max_attempts + 1):
            patch = await run_agent_async(step, current_state, registry=registry, attempt=attempt)
            current_state = _copy_model(current_state, update=patch)
            last_result = current_state.step_results[-1]
            if last_result.status == "success":
                success = True
                break
            decision = classify_step_decision(step, last_result, current_state.plan_policy)
            if decision == "retry":
                continue
            if decision == "skip":
                completed_with_degradation = True
                skipped_steps = _set_step_status(current_state.execution_steps, step.step_id, "skipped")
                current_state = _copy_model(current_state, update={"execution_steps": skipped_steps})
                current_state = _append_step_result(current_state, StepResult(
                    step_id=step.step_id,
                    agent=step.agent,
                    action=step.action,
                    status="skipped",
                    attempt=last_result.attempt,
                    latency_ms=last_result.latency_ms,
                    writes=last_result.writes,
                    error_code=last_result.error_code,
                    error=last_result.error,
                    skipped=True,
                ))
                success = True
                break
            if decision == "degrade":
                completed_with_degradation = True
                degraded_steps = _set_step_status(current_state.execution_steps, step.step_id, "degraded_success")
                current_state = _copy_model(current_state, update={"execution_steps": degraded_steps})
                current_state = _append_step_result(current_state, StepResult(
                    step_id=step.step_id,
                    agent=step.agent,
                    action=step.action,
                    status="degraded_success",
                    attempt=last_result.attempt,
                    latency_ms=last_result.latency_ms,
                    writes=last_result.writes,
                    error_code=last_result.error_code,
                    error=last_result.error,
                    degraded=True,
                ))
                success = True
                break
            break

        if not success:
            failed_steps = _set_step_status(current_state.execution_steps, step.step_id, "failed")
            reply = current_state.reply_message or f"计划执行失败：步骤 {step.action} 未成功完成。"
            current_state = _copy_model(current_state, update={
                "execution_steps": failed_steps,
                "plan_status": "failed",
                "last_plan_error": current_state.step_results[-1].error or current_state.step_results[-1].error_code,
                "replan_candidate": should_replan_after_step_failure(step, current_state.step_results[-1], current_state),
                "reply_message": reply,
            })
            return _dump_model(current_state)

        if current_state.execution_steps[index].status in {"skipped", "degraded_success"}:
            continue
        success_steps = _set_step_status(current_state.execution_steps, step.step_id, "success")
        current_state = _copy_model(current_state, update={"execution_steps": success_steps})

    current_state = _copy_model(current_state, update={
        "plan_status": "partial" if completed_with_degradation else "success",
        "reply_message": current_state.reply_message,
    })
    return _dump_model(current_state)
