"""Tests for agent contracts, registry, and runtime wrapper."""
# pytest backend/test/agent/test_agent_runtime.py -sv
from __future__ import annotations

import asyncio

import pytest

from agents.contracts import AGENT_CONTRACTS, get_agent_contract
from agents.registry import AgentRegistry, build_default_registry
from agents.runtime import run_agent_async
from workflow.state import CopilotState


def test_runtime_accepts_patch_that_matches_contract():
    registry = AgentRegistry()

    async def _executor(state: CopilotState) -> dict:
        return {"job": {"id": "job_1"}, "reply_message": "ok"}

    registry.register("jd_agent", _executor)

    result = asyncio.run(run_agent_async("jd_agent", CopilotState(session_id="sess_1"), registry=registry))

    assert result["job"] == {"id": "job_1"}
    assert result["reply_message"] == "ok"
    assert len(result["step_results"]) == 1
    assert result["step_results"][0].status == "success"


def test_runtime_filters_disallowed_patch_fields_and_records_violation():
    registry = AgentRegistry()

    async def _executor(state: CopilotState) -> dict:
        return {"job": {"id": "job_1"}, "resume_html": {"html": "<html></html>"}}

    registry.register("jd_agent", _executor)

    result = asyncio.run(run_agent_async("jd_agent", CopilotState(session_id="sess_2"), registry=registry))

    assert "job" in result
    assert "resume_html" not in result
    assert len(result["contract_violations"]) == 1
    assert result["contract_violations"][0].field == "resume_html"
    assert result["step_results"][0].status == "contract_violation"


def test_runtime_records_failure_when_executor_raises():
    registry = AgentRegistry()

    async def _executor(state: CopilotState) -> dict:
        raise RuntimeError("boom")

    registry.register("jd_agent", _executor)

    result = asyncio.run(run_agent_async("jd_agent", CopilotState(session_id="sess_3"), registry=registry))

    assert "job" not in result
    assert len(result["step_results"]) == 1
    assert result["step_results"][0].status == "failed"
    assert "boom" in result["step_results"][0].error


def test_contracts_cover_all_builtin_agents():
    expected = {
        "planner",
        "jd_agent",
        "profile_agent",
        "gap_agent",
        "content_agent",
        "render_agent",
        "interview_agent",
    }
    assert expected.issubset(set(AGENT_CONTRACTS.keys()))
    assert "job" in get_agent_contract("jd_agent").allowed_writes


def test_default_registry_registers_all_builtin_agents():
    pytest.importorskip("langchain_core")
    registry = build_default_registry()

    assert registry.names() == [
        "content_agent",
        "gap_agent",
        "interview_agent",
        "jd_agent",
        "planner",
        "profile_agent",
        "render_agent",
    ]
    assert registry.has("planner") is True
    assert registry.get_contract("render_agent").name == "render_agent"
