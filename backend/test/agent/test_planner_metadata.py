"""Tests for planner metadata helpers without LLM/runtime dependencies."""

from __future__ import annotations

from agents.planner_metadata import build_execution_plan, build_execution_steps, build_plan_metadata
from workflow.state import CandidateProfile, CopilotState, ProfileBasic


def test_build_execution_plan_for_upload_profile():
    state = CopilotState(
        session_id="sess_plan_profile",
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    plan = build_execution_plan("upload_profile", state)

    assert plan == ["profile_agent", "content_agent", "render_agent", "interview_agent"]


def test_build_execution_plan_for_upload_jd_without_profile_returns_single_step():
    state = CopilotState(session_id="sess_plan_jd")

    plan = build_execution_plan("upload_jd", state)

    assert plan == ["jd_agent"]


def test_build_execution_steps_mirrors_contract_reads_and_writes():
    steps = build_execution_steps(["jd_agent", "content_agent"], plan_id="plan_test")

    assert [step.agent for step in steps] == ["jd_agent", "content_agent"]
    assert steps[0].step_id == "plan_test_st_01"
    assert "job" in steps[0].writes
    assert "resume_content_json" in steps[1].writes


def test_build_plan_metadata_returns_plan_id_plan_and_steps():
    state = CopilotState(
        session_id="sess_plan_metadata",
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    plan_id, plan, steps = build_plan_metadata("upload_jd", state)

    assert plan_id.startswith("plan_")
    assert plan == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]
    assert [step.agent for step in steps] == plan
