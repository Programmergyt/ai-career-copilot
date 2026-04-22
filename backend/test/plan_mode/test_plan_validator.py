"""Unit tests for serial Plan Mode validation."""

from __future__ import annotations

import pytest

from agents.registry import AgentRegistry
from workflow.plan_mode.plan_schema import Plan, PlanPolicy, PlanStep, StepPrecondition, StepRetryPolicy
from workflow.plan_mode.plan_validator import PlanValidationError, validate_plan
from workflow.state import CandidateProfile, CopilotState, ProfileBasic


def _registry() -> AgentRegistry:
    registry = AgentRegistry()

    async def _ok_executor(state):
        return {}

    for agent_name in (
        "jd_agent",
        "content_agent",
        "render_agent",
        "profile_agent",
        "gap_agent",
        "interview_agent",
        "question_answer_agent",
    ):
        registry.register(agent_name, _ok_executor)
    return registry


def test_validator_accepts_valid_serial_plan():
    state = CopilotState(candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")))
    plan = Plan(
        plan_id="plan_1",
        intent="upload_jd",
        policy=PlanPolicy(),
        steps=[
            PlanStep(
                step_id="st_1",
                agent="jd_agent",
                action="parse_job",
                intent="upload_jd",
                reads=["user_message", "job", "meta", "user_attachments"],
                writes=["job", "meta", "reply_message"],
            ),
            PlanStep(
                step_id="st_2",
                agent="content_agent",
                action="generate_resume_content",
                intent="upload_jd",
                reads=["job", "candidate_profile", "gaps", "resume_content_json", "current_intent", "user_message", "meta"],
                writes=["resume_content_json", "meta", "reply_message"],
                depends_on=["st_1"],
                preconditions=[StepPrecondition(kind="job_exists"), StepPrecondition(kind="candidate_profile_exists")],
                retry=StepRetryPolicy(max_attempts=2, backoff="fixed_1s"),
            ),
        ],
    )

    validate_plan(plan, state, _registry())


def test_validator_rejects_unknown_agent():
    plan = Plan(
        plan_id="plan_2",
        intent="upload_jd",
        steps=[
            PlanStep(step_id="st_1", agent="missing_agent", action="noop", intent="upload_jd"),
        ],
    )

    with pytest.raises(PlanValidationError, match="Unknown agent"):
        validate_plan(plan, CopilotState(), _registry())


def test_validator_rejects_invalid_writes():
    plan = Plan(
        plan_id="plan_3",
        intent="render_edit",
        steps=[
            PlanStep(
                step_id="st_1",
                agent="render_agent",
                action="render_resume",
                intent="render_edit",
                writes=["resume_content_json"],
            ),
        ],
    )

    with pytest.raises(PlanValidationError, match="writes fields outside contract"):
        validate_plan(plan, CopilotState(), _registry())


def test_validator_rejects_unknown_dependency():
    plan = Plan(
        plan_id="plan_4",
        intent="render_edit",
        steps=[
            PlanStep(
                step_id="st_1",
                agent="render_agent",
                action="render_resume",
                intent="render_edit",
                depends_on=["st_missing"],
            ),
        ],
    )

    with pytest.raises(PlanValidationError, match="depends on unknown step"):
        validate_plan(plan, CopilotState(), _registry())


def test_validator_rejects_cyclic_plan():
    plan = Plan(
        plan_id="plan_5",
        intent="render_edit",
        steps=[
            PlanStep(step_id="st_1", agent="render_agent", action="render_resume", intent="render_edit", depends_on=["st_2"]),
            PlanStep(step_id="st_2", agent="content_agent", action="generate_resume_content", intent="content_edit", depends_on=["st_1"]),
        ],
    )

    with pytest.raises(PlanValidationError, match="contains a cycle"):
        validate_plan(plan, CopilotState(), _registry())


def test_validator_rejects_unsatisfied_precondition():
    plan = Plan(
        plan_id="plan_6",
        intent="render_edit",
        steps=[
            PlanStep(
                step_id="st_1",
                agent="render_agent",
                action="render_resume",
                intent="render_edit",
                preconditions=[StepPrecondition(kind="resume_content_exists")],
            ),
        ],
    )

    with pytest.raises(PlanValidationError, match="unsatisfied preconditions"):
        validate_plan(plan, CopilotState(), _registry())
