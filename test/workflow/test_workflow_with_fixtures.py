"""Workflow 集成测试：使用 fixtures 实际文件，且启用 LangSmith 监控。"""

from __future__ import annotations

import pytest

from workflow.graph import compile_graph
from workflow.state import CopilotState, Job, CandidateProfile, ProfileBasic
from test.test_support import (
    PromptRouterLLM,
    patch_all_agent_llm,
    read_fixture_text,
    ensure_langsmith_enabled,
)


@pytest.fixture(scope="module", autouse=True)
def _langsmith_monitoring():
    ensure_langsmith_enabled()


@pytest.fixture
def fixture_jd_text() -> str:
    return read_fixture_text("jds", "SAP_AIGC工程师.md")


@pytest.fixture
def fixture_profile_text() -> str:
    return read_fixture_text("profiles", "基本信息样例.md")


def test_workflow_upload_jd_runs_to_render(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    graph = compile_graph()
    state = CopilotState(
        session_id="sess_wf_jd",
        user_message=fixture_jd_text,
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="郭奕廷")),
    )

    result = graph.invoke(state.model_dump())
    final_state = CopilotState.model_validate(result)

    assert final_state.current_intent == "upload_jd"
    assert final_state.job is not None
    assert final_state.resume_content_json is not None
    assert final_state.resume_html.html
    assert "jd_agent" in final_state.triggered_agents
    assert final_state.meta.active_html_version >= 1


def test_workflow_upload_profile_runs_to_render(monkeypatch, fixture_jd_text, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_profile")
    patch_all_agent_llm(monkeypatch, llm)

    graph = compile_graph()
    state = CopilotState(
        session_id="sess_wf_profile",
        user_message=fixture_profile_text,
        job=Job(id="job_wf", title="AIGC工程师", source=fixture_jd_text),
    )

    result = graph.invoke(state.model_dump())
    final_state = CopilotState.model_validate(result)

    assert final_state.current_intent == "upload_profile"
    assert final_state.candidate_profile is not None
    assert final_state.candidate_profile.profile_basic.name == "郭奕廷"
    assert final_state.resume_content_json is not None
    assert final_state.resume_html.html
    assert "profile_agent" in final_state.triggered_agents
    assert final_state.meta.active_resume_content_version >= 1
