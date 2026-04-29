"""Agent 节点测试：使用 fixtures 实际文件，且启用 LangSmith 监控。"""
# python -m pytest backend/test/agent/test_agent_nodes.py -sv
from __future__ import annotations

import json

import pytest

from agents.planner import planner_node
from agents.jd_agent import jd_node
from agents.profile_agent import profile_node
from agents.gap_agent import gap_node
from agents.content_agent import content_node
from agents.render_agent import render_node
from agents.interview_agent import interview_node
from agents.question_agent import question_node
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


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class BrokenThenRepairedInterviewLLM:
    def __init__(self) -> None:
        self.calls = 0

    def bind(self, **kwargs):
        return self

    def invoke(self, prompt):
        self.calls += 1
        if self.calls == 1:
            return _FakeResponse('{"interview_qa": [')
        return _FakeResponse(json.dumps({
            "interview_qa": [
                {
                    "id": "qa_1",
                    "category": "technical",
                    "question": "请介绍你的 RAG 项目。",
                    "answer": "我负责检索与生成链路的实现。",
                    "source_refs": ["projects"],
                    "version": 1,
                }
            ]
        }, ensure_ascii=False))


class AlwaysBrokenInterviewLLM:
    def bind(self, **kwargs):
        return self

    def invoke(self, prompt):
        return _FakeResponse('{"interview_qa": [{"id": "qa_1" ') 


@pytest.fixture(scope="module", autouse=True)
def _langsmith_monitoring():
    ensure_langsmith_enabled()


@pytest.fixture
def fixture_jd_text() -> str:
    return read_fixture_text("jds", "通用AIGC实习JD.md")


@pytest.fixture
def fixture_profile_text() -> str:
    return read_fixture_text("profiles", "虚拟候选人信息.md")


@pytest.fixture
def fixture_project_text() -> str:
    return read_fixture_text("profiles", "求职Agent_README.md")


def test_planner_node_builds_plan_for_upload_jd(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_planner_jd",
        user_message=fixture_jd_text,
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    updates = planner_node(state)

    assert updates["current_intent"] == "upload_jd"
    assert updates["execution_plan"] == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]
    assert updates["triggered_agents"] == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]
    assert updates["section_rationales"][-1].agent == "planner"
    assert "upload_jd" in updates["section_rationales"][-1].decision


def test_planner_node_skips_content_when_no_job(monkeypatch, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_profile")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(session_id="sess_planner_profile", user_message=fixture_profile_text)
    updates = planner_node(state)

    assert updates["current_intent"] == "upload_profile"
    assert updates["execution_plan"] == ["profile_agent", "content_agent", "render_agent", "interview_agent"]


def test_planner_node_routes_gap_analysis_to_gap_agent(monkeypatch):
    llm = PromptRouterLLM(intent="gap_analysis")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_planner_gap",
        user_message="分析一下我和这个岗位还有哪些差距",
        job=Job(id="job_1", title="AIGC工程师"),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )
    updates = planner_node(state)

    assert updates["current_intent"] == "gap_analysis"
    assert updates["execution_plan"] == ["gap_agent"]
    assert updates["triggered_agents"] == ["gap_agent"]


def test_planner_node_routes_ask_question_to_question_agent(monkeypatch):
    llm = PromptRouterLLM(intent="ask_question")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_planner_question",
        user_message="我当前的目标岗位是什么？",
        job=Job(id="job_1", title="AIGC工程师"),
    )
    updates = planner_node(state)

    assert updates["current_intent"] == "ask_question"
    assert updates["execution_plan"] == ["question_agent"]
    assert updates["triggered_agents"] == ["question_agent"]


def test_jd_node_parses_job_from_fixture(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(session_id="sess_jd", user_message=fixture_jd_text)
    updates = jd_node(state)

    job = updates["job"]
    assert job.title == "AIGC工程师"
    assert "RAG" in job.tech_stack
    assert updates["meta"].dirty_flags.content_dirty is True
    assert updates["section_rationales"][-1].agent == "jd_agent"
    assert updates["section_rationales"][-1].section == "岗位分析"


def test_profile_node_updates_candidate_profile(monkeypatch, fixture_profile_text, fixture_project_text):
    llm = PromptRouterLLM(intent="upload_profile")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_profile",
        user_message=f"{fixture_profile_text}\n\n{fixture_project_text}",
    )
    updates = profile_node(state)

    profile = updates["candidate_profile"]
    assert profile.profile_basic.name == "林知遥"
    assert len(profile.materials) == 1
    assert len(profile.facts) >= 2
    assert updates["section_rationales"][-1].agent == "profile_agent"
    assert updates["section_rationales"][-1].section == "候选人画像"


def test_gap_node_generates_gaps_and_questions(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_gap",
        user_message=fixture_jd_text,
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )
    updates = gap_node(state)

    assert updates["gaps"]
    assert updates["questions_to_ask"]
    assert updates["questions_to_ask"][0].status == "pending"
    assert updates["section_rationales"][-1].agent == "gap_agent"
    assert updates["section_rationales"][-1].section == "匹配差距"


def test_question_node_answers_from_state(monkeypatch):
    llm = PromptRouterLLM(intent="ask_question")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_question",
        user_message="我当前的目标岗位和候选人是谁？",
        job=Job(id="job_1", title="AIGC工程师"),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )
    updates = question_node(state)

    assert updates["section_rationales"][-1].agent == "question_agent"
    assert "AIGC工程师" in updates["agent_reply_message"]
    assert "林知遥" in updates["agent_reply_message"]


def test_interview_node_generates_interview_qa(monkeypatch, fixture_jd_text, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    resume_content = ResumeContent(
        profile=ResumeProfile(
            name="林知遥",
            email="lin.zhiyou@example.test",
            phone="12345678901",
            city="杭州",
            education=[
                Education(
                    id="edu_1",
                    school="星海理工大学",
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
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
        resume_content_json=resume_content,
    )
    updates = interview_node(state)

    assert updates["interview_qa"]
    assert updates["meta"].dirty_flags.interview_dirty is False
    assert updates["section_rationales"][-1].agent == "interview_agent"
    assert updates["section_rationales"][-1].section == "面试准备"


def test_content_and_render_nodes_generate_html(monkeypatch, fixture_jd_text, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_content_render",
        current_intent="upload_jd",
        user_message=fixture_jd_text,
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    content_updates = content_node(state)
    state = state.model_copy(update=content_updates)

    state = state.model_copy(update={"current_intent": "render_edit", "user_message": "改成双栏布局"})
    render_updates = render_node(state)

    assert content_updates["resume_content_json"].meta.version >= 1
    assert content_updates["section_rationales"][-1].agent == "content_agent"
    assert render_updates["render_config"].layout_mode == "double-column"
    assert "<html" in render_updates["resume_html"].html.lower()
    assert render_updates["meta"].dirty_flags.render_dirty is False
    assert render_updates["section_rationales"][-1].agent == "render_agent"


def test_interview_node_retries_once_after_invalid_json(monkeypatch, fixture_jd_text):
    llm = BrokenThenRepairedInterviewLLM()
    monkeypatch.setattr("agents.interview_agent.get_llm", lambda: llm)

    resume_content = ResumeContent(
        profile=ResumeProfile(name="林知遥"),
        summary="聚焦 AIGC 与 RAG 的候选人。",
        projects=[
            SectionItem(id="proj_1", title="AI Career Copilot", content="负责多 Agent 系统实现。", source_refs=[], updated_at=""),
        ],
        meta=ResumeContentMeta(target_role="AIGC工程师", version=1),
    )
    state = CopilotState(
        session_id="sess_interview_retry",
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
        resume_content_json=resume_content,
    )

    updates = interview_node(state)

    assert llm.calls == 2
    assert len(updates["interview_qa"]) == 1
    assert updates["section_rationales"][-1].decision.startswith("生成 1 条面试问答")


def test_interview_node_reports_failure_after_retry_exhausted(monkeypatch, fixture_jd_text):
    llm = AlwaysBrokenInterviewLLM()
    monkeypatch.setattr("agents.interview_agent.get_llm", lambda: llm)

    resume_content = ResumeContent(
        profile=ResumeProfile(name="林知遥"),
        summary="聚焦 AIGC 与 RAG 的候选人。",
        projects=[
            SectionItem(id="proj_1", title="AI Career Copilot", content="负责多 Agent 系统实现。", source_refs=[], updated_at=""),
        ],
        meta=ResumeContentMeta(target_role="AIGC工程师", version=1),
    )
    state = CopilotState(
        session_id="sess_interview_fail",
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
        resume_content_json=resume_content,
    )

    updates = interview_node(state)

    assert updates["interview_qa"] == []
    assert updates["section_rationales"][-1].reason == "模型返回的面试问答不符合 JSON 约束，请重试。"
    assert updates["section_rationales"][-1].status == "failed"
    assert "meta" not in updates
