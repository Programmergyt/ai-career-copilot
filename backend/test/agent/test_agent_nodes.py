"""Agent 节点测试：使用 fixtures 实际文件，且启用 LangSmith 监控。"""

from __future__ import annotations

import pytest

from agents.planner import planner_node
from agents.jd_agent import jd_node
from agents.profile_agent import profile_node
from agents.gap_agent import gap_node
from agents.content_agent import content_node
from agents.render_agent import render_node
from agents.interview_agent import interview_node
from workflow.state import (
    CopilotState, Job, CandidateProfile, ProfileBasic,
    ResumeContent, ResumeProfile, ResumeContentMeta, SectionItem, Education,
)
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


@pytest.fixture
def fixture_project_text() -> str:
    return read_fixture_text("projects", "求职Agent_README.md")


def test_planner_node_builds_plan_for_upload_jd(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_planner_jd",
        user_message=fixture_jd_text,
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="郭奕廷")),
    )

    updates = planner_node(state)

    assert updates["current_intent"] == "upload_jd"
    assert updates["execution_plan"] == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]
    assert updates["triggered_agents"] == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]


def test_planner_node_skips_content_when_no_job(monkeypatch, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_profile")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(session_id="sess_planner_profile", user_message=fixture_profile_text)
    updates = planner_node(state)

    assert updates["current_intent"] == "upload_profile"
    assert updates["execution_plan"] == ["profile_agent", "content_agent", "render_agent", "interview_agent"]


def test_jd_node_parses_job_from_fixture(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(session_id="sess_jd", user_message=fixture_jd_text)
    updates = jd_node(state)

    job = updates["job"]
    assert job.title == "AIGC工程师"
    assert "RAG" in job.tech_stack
    assert updates["meta"].dirty_flags.content_dirty is True


def test_profile_node_updates_candidate_profile(monkeypatch, fixture_profile_text, fixture_project_text):
    llm = PromptRouterLLM(intent="upload_profile")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_profile",
        user_message=f"{fixture_profile_text}\n\n{fixture_project_text}",
    )
    updates = profile_node(state)

    profile = updates["candidate_profile"]
    assert profile.profile_basic.name == "郭奕廷"
    assert len(profile.materials) == 1
    assert len(profile.facts) >= 2


def test_gap_node_generates_gaps_and_questions(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_gap",
        user_message=fixture_jd_text,
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="郭奕廷")),
    )
    updates = gap_node(state)

    assert updates["gaps"]
    assert updates["questions_to_ask"]
    assert updates["questions_to_ask"][0].status == "pending"


def test_interview_node_generates_interview_qa(monkeypatch, fixture_jd_text, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    resume_content = ResumeContent(
        profile=ResumeProfile(
            name="郭奕廷",
            email="2403508140@qq.com",
            phone="12345678901",
            city="上海",
            education=[
                Education(
                    id="edu_1",
                    school="华东理工大学",
                    major="控制工程",
                    degree="硕士",
                    start_date="2025-09",
                    end_date="2028-06",
                )
            ],
        ),
        summary="聚焦 AIGC 与 RAG 的候选人。",
        skills=[
            SectionItem(id="skill_1", title="Python", content="熟练使用 Python 和 LangChain。", source_refs=[], updated_at=""),
        ],
        projects=[
            SectionItem(id="proj_1", title="AI Career Copilot", content="负责多 Agent 简历系统的设计与实现。", source_refs=[], updated_at=""),
        ],
        meta=ResumeContentMeta(target_role="AIGC工程师", version=1),
    )

    state = CopilotState(
        session_id="sess_interview",
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="郭奕廷")),
        resume_content_json=resume_content,
    )
    updates = interview_node(state)

    assert updates["interview_qa"]
    assert updates["meta"].dirty_flags.interview_dirty is False


def test_content_and_render_nodes_generate_html(monkeypatch, fixture_jd_text, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_content_render",
        current_intent="upload_jd",
        user_message=fixture_jd_text,
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="郭奕廷")),
    )

    content_updates = content_node(state)
    state = state.model_copy(update=content_updates)

    state = state.model_copy(update={"current_intent": "render_edit", "user_message": "改成双栏布局"})
    render_updates = render_node(state)

    assert content_updates["resume_content_json"].meta.version >= 1
    assert render_updates["render_config"].layout_mode == "double-column"
    assert "<html" in render_updates["resume_html"].html.lower()
    assert render_updates["meta"].dirty_flags.render_dirty is False
