"""Workflow 集成测试：使用 fixtures 实际文件，且启用 LangSmith 监控。

这些测试会留下 workflow 级 trace，用于观察 LangGraph 的节点编排是否按预期执行。
测试中虽然使用了真实 fixture 文本，但各 Agent 的 LLM 调用都被 PromptRouterLLM
替换为可预测的假实现，因此 trace 反映的是工作流路径，而不是真实模型质量。
"""

from __future__ import annotations

import asyncio

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
    return read_fixture_text("jds", "通用AIGC实习JD.md")


@pytest.fixture
def fixture_profile_text() -> str:
    return read_fixture_text("profiles", "虚拟候选人信息.md")


def test_workflow_upload_jd_runs_to_render(monkeypatch, fixture_jd_text):
    """验证上传 JD 后，整条 pipeline 会从岗位解析推进到 HTML 渲染。

    LangSmith trace 名称：Test-Workflow: Upload JD to Render

    这个测试的目的不是验证真实 JD 解析质量，而是验证：
    1. planner 能把输入识别为 upload_jd；
    2. graph 会依次走 jd_agent -> content_agent -> render_agent；
    3. 最终状态中会产出岗位、简历内容和 HTML。
    """
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    graph = compile_graph()
    state = CopilotState(
        session_id="sess_wf_jd",
        user_message=fixture_jd_text,
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    # 输入由两部分组成：
    # 1. 真实 JD fixture 文本；
    # 2. 一个最小候选人画像，只提供姓名，确保 content/render 阶段可继续执行。
    # 这里不会访问 config.yaml 中配置的真实 LLM API，因为 get_llm 已被 monkeypatch。
    result = asyncio.run(graph.ainvoke(
        state.model_dump(),
        config={"run_name": "Test-Workflow: Upload JD to Render"},
    ))
    final_state = CopilotState.model_validate(result)

    assert final_state.current_intent == "upload_jd"
    assert final_state.job is not None
    assert final_state.resume_content_json is not None
    assert final_state.resume_html.html
    assert "jd_agent" in final_state.triggered_agents
    assert final_state.meta.active_html_version >= 1


def test_workflow_upload_profile_runs_to_render(monkeypatch, fixture_jd_text, fixture_profile_text):
    """验证上传个人资料后，系统会基于既有 JD 生成并渲染简历。

    LangSmith trace 名称：Test-Workflow: Upload Profile to Render

    这个测试尤其要注意输入与输出的语义边界：
    1. 输入中提供了 profile fixture 和预置 job；
    2. profile_agent/content_agent 调用的仍是假 LLM；
    3. 因此最终 HTML 中的项目经历、实习经历可能来自测试桩返回的固定 JSON，
       而不是完全由 user_message 现场抽取得到。
    """
    llm = PromptRouterLLM(intent="upload_profile")
    patch_all_agent_llm(monkeypatch, llm)

    graph = compile_graph()
    state = CopilotState(
        session_id="sess_wf_profile",
        user_message=fixture_profile_text,
        job=Job(id="job_wf", title="AIGC工程师", source=fixture_jd_text),
    )

    # 输入由两部分组成：
    # 1. 真实的个人资料文本；
    # 2. 预置好的 job，上下文明确目标岗位，允许 content_agent 直接生成简历内容。
    # trace 重点反映 workflow 的状态流转，不代表真实模型按输入逐字抽取了所有内容。
    result = asyncio.run(graph.ainvoke(
        state.model_dump(),
        config={"run_name": "Test-Workflow: Upload Profile to Render"},
    ))
    final_state = CopilotState.model_validate(result)

    assert final_state.current_intent == "upload_profile"
    assert final_state.candidate_profile is not None
    assert final_state.candidate_profile.profile_basic.name == "林知遥"
    assert final_state.resume_content_json is not None
    assert final_state.resume_html.html
    assert "profile_agent" in final_state.triggered_agents
    assert final_state.meta.active_resume_content_version >= 1
