"""Tests for planner plan-building helpers without LLM/runtime dependencies."""

from __future__ import annotations

from workflow.plan_mode.plan_builder import build_plan_from_tasks
from agents.planner_metadata import build_plan, build_plan_metadata
from workflow.state import CandidateProfile, CopilotState, ProfileBasic


def test_build_plan_for_upload_profile_without_job_skips_interview():
    state = CopilotState(
        session_id="sess_plan_profile",
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    plan = build_plan("upload_profile", state)

    assert [step.agent for step in plan.steps] == ["profile_agent", "content_agent", "render_agent"]


def test_build_plan_for_upload_jd_without_profile_returns_single_step():
    state = CopilotState(session_id="sess_plan_jd")

    plan = build_plan("upload_jd", state)

    assert [step.agent for step in plan.steps] == ["jd_agent"]


def test_build_plan_steps_include_actions_and_preconditions():
    state = CopilotState(
        session_id="sess_plan_content",
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )
    plan = build_plan("upload_jd", state)

    assert plan.steps[0].action == "parse_job"
    assert plan.steps[1].depends_on == [plan.steps[0].step_id]
    assert [item.kind for item in plan.steps[1].preconditions] == ["job_exists", "candidate_profile_exists"]
    assert plan.steps[2].retry.max_attempts == 2
    assert plan.steps[0].writes == ["job"]


def test_build_plan_metadata_returns_plan_id_plan_and_steps():
    state = CopilotState(
        session_id="sess_plan_metadata",
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    plan, execution_plan = build_plan_metadata("upload_jd", state)

    assert plan.plan_id.startswith("plan_")
    assert execution_plan == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]
    assert [step.agent for step in plan.steps] == execution_plan


def test_dynamic_plan_builder_supports_content_and_render_bundle():
    state = CopilotState(
        session_id="sess_bundle",
        user_message="帮我优化项目描述并改成双栏布局",
    )

    plan = build_plan_from_tasks(["content_edit", "render_edit"], state, primary_intent="content_edit")

    assert plan.intent_bundle == ["content_edit", "render_edit"]
    assert [step.action for step in plan.steps] == ["update_resume_content", "update_render_config"]
    assert plan.steps[1].depends_on == [plan.steps[0].step_id]


def test_build_plan_for_gap_analysis_routes_to_gap_agent():
    state = CopilotState(session_id="sess_gap_analysis")

    plan = build_plan("gap_analysis", state)

    assert [step.agent for step in plan.steps] == ["gap_agent"]
    assert [step.action for step in plan.steps] == ["analyze_gap"]


def test_build_plan_for_ask_question_routes_to_question_answer_agent():
    state = CopilotState(session_id="sess_qa", user_message="这个岗位更看重什么")

    plan = build_plan("ask_question", state)

    assert [step.agent for step in plan.steps] == ["question_answer_agent"]
    assert [step.action for step in plan.steps] == ["answer_question"]
