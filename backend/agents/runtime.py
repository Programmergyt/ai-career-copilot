"""Runtime wrapper that executes agents through registry + contract checks."""

from __future__ import annotations

import time
import uuid
from typing import Any

from agents.registry import AgentRegistry, get_default_registry
from log import get_logger
from workflow.plan_mode.plan_schema import ContractViolation, PlanStep, StepResult
from workflow.state import CopilotState

logger = get_logger("agent")

_RUNTIME_MANAGED_FIELDS = {"step_results", "contract_violations"}


def _copy_model(model: Any, **kwargs):
    if hasattr(model, "model_copy"):
        return model.model_copy(**kwargs)
    return model.copy(**kwargs)


def _build_step_result(
    step_id: str,
    agent_name: str,
    action: str,
    *,
    status: str,
    attempt: int,
    latency_ms: int,
    writes: list[str],
    error_code: str = "",
    error: str = "",
    degraded: bool = False,
    skipped: bool = False,
) -> StepResult:
    return StepResult(
        step_id=step_id,
        agent=agent_name,
        action=action,
        status=status,
        attempt=attempt,
        latency_ms=latency_ms,
        writes=writes,
        error_code=error_code,
        error=error,
        degraded=degraded,
        skipped=skipped,
    )


def _build_violations(step_id: str, agent_name: str, action: str, fields: list[str]) -> list[ContractViolation]:
    return [
        ContractViolation(
            step_id=step_id,
            agent=agent_name,
            action=action,
            field=field,
            reason="write_not_allowed_by_contract",
        )
        for field in fields
    ]


def _normalize_runtime_target(target: str | PlanStep) -> tuple[str, str, str]:
    if isinstance(target, PlanStep):
        return target.step_id, target.agent, target.action
    step_id = f"step_{uuid.uuid4().hex[:12]}"
    return step_id, target, target


async def run_agent_async(
    target: str | PlanStep,
    state: CopilotState,
    *,
    registry: AgentRegistry | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    """Execute a registered agent and attach runtime validation metadata."""

    step_id, agent_name, action = _normalize_runtime_target(target)
    track_step_result = not (isinstance(target, str) and agent_name == "planner")
    active_step = target if isinstance(target, PlanStep) else None
    active_registry = registry or get_default_registry()
    executor = active_registry.get_executor(agent_name)
    contract = active_registry.get_contract(agent_name)
    started = time.perf_counter()
    execution_state = state
    if active_step is not None:
        execution_state = _copy_model(state, update={
            "active_step": active_step,
            "current_intent": active_step.intent,
        })

    try:
        patch = await executor(execution_state)
        if patch is None:
            patch = {}
        if not isinstance(patch, dict):
            raise TypeError(f"Agent {agent_name} must return dict, got {type(patch)!r}")
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("Agent runtime failed for %s", agent_name)
        if not track_step_result:
            return {}
        return {
            "step_results": [
                *state.step_results,
                _build_step_result(
                    step_id,
                    agent_name,
                    action,
                    status="failed",
                    attempt=attempt,
                    latency_ms=latency_ms,
                    writes=[],
                    error_code="runtime_exception",
                    error=str(exc),
                ),
            ]
        }

    raw_write_fields = sorted(set(patch.keys()) - _RUNTIME_MANAGED_FIELDS)
    invalid_fields = sorted(field for field in raw_write_fields if field not in contract.allowed_writes)
    allowed_patch = {key: value for key, value in patch.items() if key in contract.allowed_writes}
    latency_ms = int((time.perf_counter() - started) * 1000)

    if invalid_fields:
        violations = _build_violations(step_id, agent_name, action, invalid_fields)
        logger.warning("Contract violation for %s: %s", agent_name, ", ".join(invalid_fields))
        if not track_step_result:
            return {
                **allowed_patch,
                "contract_violations": [*state.contract_violations, *violations],
            }
        return {
            **allowed_patch,
            "contract_violations": [*state.contract_violations, *violations],
            "step_results": [
                *state.step_results,
                _build_step_result(
                    step_id,
                    agent_name,
                    action,
                    status="contract_violation",
                    attempt=attempt,
                    latency_ms=latency_ms,
                    writes=sorted(allowed_patch.keys()),
                    error_code="contract_violation",
                    error=",".join(invalid_fields),
                ),
            ],
        }

    expected_writes: list[str] = []
    if active_step is not None:
        expected_writes = [field for field in active_step.writes if field not in _RUNTIME_MANAGED_FIELDS]
        missing_expected = [field for field in expected_writes if field not in allowed_patch]
        if missing_expected:
            if not track_step_result:
                return allowed_patch
            return {
                **allowed_patch,
                "step_results": [
                    *state.step_results,
                    _build_step_result(
                        step_id,
                        agent_name,
                        action,
                        status="failed",
                        attempt=attempt,
                        latency_ms=latency_ms,
                        writes=sorted(allowed_patch.keys()),
                        error_code="missing_expected_writes",
                        error=",".join(missing_expected),
                    ),
                ],
            }

    if not track_step_result:
        return allowed_patch

    return {
        **allowed_patch,
        "step_results": [
            *state.step_results,
            _build_step_result(
                step_id,
                agent_name,
                action,
                status="success",
                attempt=attempt,
                latency_ms=latency_ms,
                writes=sorted(allowed_patch.keys()),
            ),
        ],
    }


def make_runtime_node(agent_name: str, *, registry: AgentRegistry | None = None):
    """Create a LangGraph-compatible async node using the shared runtime."""

    async def _node(state: CopilotState) -> dict[str, Any]:
        return await run_agent_async(agent_name, state, registry=registry)

    return _node
