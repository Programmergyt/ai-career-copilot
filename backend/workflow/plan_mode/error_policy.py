"""Error classification and executor fallback decisions."""

from __future__ import annotations

from typing import Literal

from workflow.plan_mode.plan_schema import PlanPolicy, PlanStep, StepResult


StepDecision = Literal["retry", "fail", "skip", "degrade"]

_RETRYABLE_ERROR_CODES = {
    "runtime_exception",
    "missing_expected_writes",
}


def classify_step_decision(
    step: PlanStep,
    result: StepResult,
    policy: PlanPolicy,
) -> StepDecision:
    """Return the executor decision for a failed step result."""
    if result.status == "contract_violation" or result.error_code == "precondition_failed":
        return "fail"

    if result.status == "failed" and result.error_code in _RETRYABLE_ERROR_CODES:
        if result.attempt < step.retry.max_attempts:
            return "retry"

    if step.on_error == "skip" and step.skippable and policy.partial_success:
        return "skip"

    if step.on_error == "degrade" and step.skippable and policy.allow_degraded_completion:
        return "degrade"

    return "fail"
