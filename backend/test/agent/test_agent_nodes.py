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
from workflow.plan_mode.plan_schema import PlanStep
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
            return _FakeResponse('{"interview_qa": [{"id": "qa_1", "question": "bad"}')
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
    return read_fixture_text("projects", "求职Agent_README.md")


def test_planner_node_builds_plan_for_upload_jd(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_planner_jd",
        user_message=fixture_jd_text,
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    updates = planner_node(state)

    assert updates["active_plan_id"].startswith("plan_")
    assert updates["current_intent"] == "upload_jd"
    assert updates["intent_bundle"] == ["upload_jd"]
    assert updates["plan_status"] == "planned"
    assert updates["execution_plan"] == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]
    assert [step.agent for step in updates["execution_steps"]] == updates["execution_plan"]
    assert updates["execution_steps"][0].action == "parse_job"
    assert updates["execution_steps"][0].reads
    assert updates["execution_steps"][0].writes
    assert updates["triggered_agents"] == ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"]


def test_planner_node_skips_content_when_no_job(monkeypatch, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_profile")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(session_id="sess_planner_profile", user_message=fixture_profile_text)
    updates = planner_node(state)

    assert updates["active_plan_id"].startswith("plan_")
    assert updates["current_intent"] == "upload_profile"
    assert updates["intent_bundle"] == ["upload_profile"]
    assert updates["execution_plan"] == ["profile_agent", "content_agent", "render_agent"]
    assert [step.agent for step in updates["execution_steps"]] == updates["execution_plan"]


def test_planner_node_builds_single_step_plan_when_profile_missing(monkeypatch, fixture_jd_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(session_id="sess_planner_single_step", user_message=fixture_jd_text)
    updates = planner_node(state)

    assert updates["execution_plan"] == ["jd_agent"]
    assert len(updates["execution_steps"]) == 1
    assert updates["execution_steps"][0].agent == "jd_agent"
    assert updates["execution_steps"][0].action == "parse_job"


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
    assert profile.profile_basic.name == "林知遥"
    assert len(profile.materials) == 1
    assert len(profile.facts) >= 2


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


def test_content_and_render_nodes_generate_html(monkeypatch, fixture_jd_text, fixture_profile_text):
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state = CopilotState(
        session_id="sess_content_render",
        user_message=fixture_jd_text,
        job=Job(id="job_1", title="AIGC工程师", source=fixture_jd_text),
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
        active_step=PlanStep(
            step_id="st_content",
            agent="content_agent",
            action="generate_resume_content",
            intent="upload_jd",
            params={"mode": "generate"},
        ),
    )

    content_updates = content_node(state)
    state = state.model_copy(update=content_updates)

    state = state.model_copy(update={
        "user_message": "改成双栏布局",
        "active_step": PlanStep(
            step_id="st_render",
            agent="render_agent",
            action="update_render_config",
            intent="render_edit",
            params={"mode": "edit", "instruction": "改成双栏布局"},
        ),
    })
    render_updates = render_node(state)

    assert content_updates["resume_content_json"].meta.version >= 1
    assert render_updates["render_config"].layout_mode == "double-column"
    assert "<html" in render_updates["resume_html"].html.lower()
    assert render_updates["meta"].dirty_flags.render_dirty is False


def test_interview_node_retries_once_after_invalid_json(monkeypatch, fixture_jd_text):
    llm = BrokenThenRepairedInterviewLLM()
    monkeypatch.setattr("agents.implementations.interview_agent.get_llm", lambda: llm)

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
    assert updates["reply_message"].startswith("面试问答已生成")


def test_interview_node_reports_failure_after_retry_exhausted(monkeypatch, fixture_jd_text):
    llm = AlwaysBrokenInterviewLLM()
    monkeypatch.setattr("agents.implementations.interview_agent.get_llm", lambda: llm)

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
    assert updates["reply_message"] == "面试问答生成失败：模型输出格式异常，请重试。"
    assert "meta" not in updates
