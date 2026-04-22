"""Unit tests for serial Plan Mode executor."""

from __future__ import annotations

import asyncio

from agents.registry import AgentRegistry
from workflow.plan_mode.plan_executor import plan_executor_node_async
from workflow.plan_mode.plan_schema import PlanPolicy, PlanStep, StepPrecondition, StepRetryPolicy
from workflow.state import CopilotState


def _registry_with(*, render_returns_violation: bool = False, content_fail_once: bool = False) -> AgentRegistry:
    registry = AgentRegistry()
    call_counts = {"content": 0}

    async def _jd(state: CopilotState):
        return {"job": {"id": "job_1"}, "reply_message": "jd ok"}

    async def _content(state: CopilotState):
        call_counts["content"] += 1
        if content_fail_once and call_counts["content"] == 1:
            raise RuntimeError("temporary content failure")
        return {"resume_content_json": {"summary": "ok"}, "reply_message": "content ok"}

    async def _render(state: CopilotState):
        if render_returns_violation:
            return {"resume_html": {"html": "<html></html>"}, "resume_content_json": {"summary": "bad"}}
        return {"resume_html": {"html": "<html></html>"}, "reply_message": "render ok"}

    registry.register("jd_agent", _jd)
    registry.register("content_agent", _content)
    registry.register("render_agent", _render)
    return registry


def _restore_state(result: dict) -> CopilotState:
    if hasattr(CopilotState, "model_validate"):
        return CopilotState.model_validate(result)
    return CopilotState.parse_obj(result)


def test_executor_runs_single_step_successfully(monkeypatch):
    monkeypatch.setattr("workflow.plan_mode.plan_executor.get_default_registry", lambda: _registry_with())
    state = CopilotState(
        execution_steps=[
            PlanStep(step_id="st_1", agent="jd_agent", action="parse_job", intent="upload_jd"),
        ],
        execution_plan=["jd_agent"],
        plan_status="planned",
    )

    result = _restore_state(asyncio.run(plan_executor_node_async(state)))

    assert result.plan_status == "success"
    assert result.step_results[-1].status == "success"


def test_executor_runs_multiple_steps_in_order(monkeypatch):
    monkeypatch.setattr("workflow.plan_mode.plan_executor.get_default_registry", lambda: _registry_with())
    state = CopilotState(
        execution_steps=[
            PlanStep(step_id="st_1", agent="jd_agent", action="parse_job", intent="upload_jd"),
            PlanStep(
                step_id="st_2",
                agent="content_agent",
                action="generate_resume_content",
                intent="upload_jd",
                depends_on=["st_1"],
                preconditions=[StepPrecondition(kind="job_exists")],
            ),
        ],
        execution_plan=["jd_agent", "content_agent"],
    )

    result = _restore_state(asyncio.run(plan_executor_node_async(state)))

    assert result.plan_status == "success"
    assert [step.status for step in result.execution_steps] == ["success", "success"]


def test_executor_stops_on_failed_step(monkeypatch):
    monkeypatch.setattr("workflow.plan_mode.plan_executor.get_default_registry", lambda: _registry_with())
    state = CopilotState(
        execution_steps=[
            PlanStep(
                step_id="st_1",
                agent="render_agent",
                action="render_resume",
                intent="render_edit",
                preconditions=[StepPrecondition(kind="resume_content_exists")],
            ),
            PlanStep(step_id="st_2", agent="jd_agent", action="parse_job", intent="upload_jd"),
        ],
        execution_plan=["render_agent", "jd_agent"],
    )

    result = _restore_state(asyncio.run(plan_executor_node_async(state)))

    assert result.plan_status == "failed"
    assert result.execution_steps[0].status == "failed"


def test_executor_records_contract_violation(monkeypatch):
    monkeypatch.setattr(
        "workflow.plan_mode.plan_executor.get_default_registry",
        lambda: _registry_with(render_returns_violation=True),
    )
    state = CopilotState(
        resume_content_json={"summary": "ready"},
        execution_steps=[
            PlanStep(
                step_id="st_1",
                agent="render_agent",
                action="render_resume",
                intent="render_edit",
                preconditions=[StepPrecondition(kind="resume_content_exists")],
            ),
        ],
        execution_plan=["render_agent"],
    )

    result = _restore_state(asyncio.run(plan_executor_node_async(state)))

    assert result.plan_status == "failed"
    assert result.contract_violations[-1].field == "resume_content_json"


def test_executor_retries_same_step(monkeypatch):
    monkeypatch.setattr(
        "workflow.plan_mode.plan_executor.get_default_registry",
        lambda: _registry_with(content_fail_once=True),
    )
    state = CopilotState(
        job={"id": "job_1"},
        execution_steps=[
            PlanStep(
                step_id="st_1",
                agent="content_agent",
                action="generate_resume_content",
                intent="upload_jd",
                retry=StepRetryPolicy(max_attempts=2, backoff="fixed_1s"),
                preconditions=[StepPrecondition(kind="job_exists")],
            ),
        ],
        execution_plan=["content_agent"],
    )

    result = _restore_state(asyncio.run(plan_executor_node_async(state)))

    assert result.plan_status == "success"
    assert [item.attempt for item in result.step_results] == [1, 2]


def test_executor_degrades_non_critical_step(monkeypatch):
    registry = AgentRegistry()

    async def _interview(state: CopilotState):
        return {"reply_message": "interview unavailable"}

    registry.register("interview_agent", _interview)
    monkeypatch.setattr("workflow.plan_mode.plan_executor.get_default_registry", lambda: registry)
    state = CopilotState(
        job={"id": "job_1"},
        candidate_profile={"profile_basic": {"name": "Lin"}},
        resume_content_json={"summary": "ok"},
        plan_policy=PlanPolicy(partial_success=True, allow_degraded_completion=True),
        execution_steps=[
            PlanStep(
                step_id="st_1",
                agent="interview_agent",
                action="generate_interview_qa",
                intent="upload_jd",
                writes=["interview_qa"],
                preconditions=[
                    StepPrecondition(kind="job_exists"),
                    StepPrecondition(kind="candidate_profile_exists"),
                    StepPrecondition(kind="resume_content_exists"),
                ],
                on_error="degrade",
                skippable=True,
            ),
        ],
        execution_plan=["interview_agent"],
    )

    result = _restore_state(asyncio.run(plan_executor_node_async(state)))

    assert result.plan_status == "partial"
    assert result.execution_steps[0].status == "degraded_success"
    assert result.step_results[-1].degraded is True
