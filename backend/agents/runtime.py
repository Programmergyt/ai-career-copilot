"""Runtime wrapper that executes agents through registry + contract checks."""

from __future__ import annotations

import time
import uuid
from typing import Any

from agents.registry import AgentRegistry, get_default_registry
from log import get_logger
from workflow.state import ContractViolation, CopilotState, StepResult

logger = get_logger("agent")

_RUNTIME_MANAGED_FIELDS = {"step_results", "contract_violations"}


def _build_step_result(
    agent_name: str,
    *,
    status: str,
    latency_ms: int,
    writes: list[str],
    error: str = "",
) -> StepResult:
    return StepResult(
        step_id=f"step_{uuid.uuid4().hex[:12]}",
        agent=agent_name,
        status=status,
        latency_ms=latency_ms,
        writes=writes,
        error=error,
    )


def _build_violations(agent_name: str, fields: list[str]) -> list[ContractViolation]:
    return [
        ContractViolation(
            agent=agent_name,
            field=field,
            reason="write_not_allowed_by_contract",
        )
        for field in fields
    ]


async def run_agent_async(
    agent_name: str,
    state: CopilotState,
    *,
    registry: AgentRegistry | None = None,
) -> dict[str, Any]:
    """Execute a registered agent and attach runtime validation metadata."""

    active_registry = registry or get_default_registry()
    executor = active_registry.get_executor(agent_name)
    contract = active_registry.get_contract(agent_name)
    started = time.perf_counter()

    try:
        patch = await executor(state)
        if patch is None:
            patch = {}
        if not isinstance(patch, dict):
            raise TypeError(f"Agent {agent_name} must return dict, got {type(patch)!r}")
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("Agent runtime failed for %s", agent_name)
        return {
            "step_results": [
                *state.step_results,
                _build_step_result(
                    agent_name,
                    status="failed",
                    latency_ms=latency_ms,
                    writes=[],
                    error=str(exc),
                ),
            ]
        }

    raw_write_fields = sorted(set(patch.keys()) - _RUNTIME_MANAGED_FIELDS)
    invalid_fields = sorted(field for field in raw_write_fields if field not in contract.allowed_writes)
    allowed_patch = {key: value for key, value in patch.items() if key in contract.allowed_writes}
    latency_ms = int((time.perf_counter() - started) * 1000)

    if invalid_fields:
        violations = _build_violations(agent_name, invalid_fields)
        logger.warning("Contract violation for %s: %s", agent_name, ", ".join(invalid_fields))
        return {
            **allowed_patch,
            "contract_violations": [*state.contract_violations, *violations],
            "step_results": [
                *state.step_results,
                _build_step_result(
                    agent_name,
                    status="contract_violation",
                    latency_ms=latency_ms,
                    writes=sorted(allowed_patch.keys()),
                    error=",".join(invalid_fields),
                ),
            ],
        }

    return {
        **allowed_patch,
        "step_results": [
            *state.step_results,
            _build_step_result(
                agent_name,
                status="success",
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
