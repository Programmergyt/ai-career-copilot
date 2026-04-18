"""真实 LLM 集成测试。

这些测试直接调用项目在 config.yaml 中配置的大模型接口，覆盖两类场景：
1. 单节点 Agent 的真实端到端行为；
2. LangGraph 整条 workflow 的真实端到端行为。

文件中的测试顺序基本按工作流依赖展开：
planner -> jd/profile -> content -> render -> full workflow。

注意：
- 为避免默认执行 `pytest test` 时产生额外成本，需在 config.yaml 中将
    `testing.integration.run_real_llm_tests` 显式设为 true 才会运行本模块；
- 本模块复用 test/fixtures 中的真实测试材料，不使用 PromptRouterLLM；
- 断言刻意保持“结构正确、语义宽松”，避免因真实模型措辞波动导致脆弱失败。

执行命令：
python -m pytest test/integration/test_real_llm_e2e.py -sv
"""

from __future__ import annotations

import uuid

import pytest

from agents.content_agent import content_node
from agents.jd_agent import jd_node
from agents.planner import planner_node
from agents.profile_agent import profile_node
from agents.render_agent import render_node
from config_loader import should_run_real_llm_integration_tests
from test.test_support import ensure_langsmith_enabled, read_fixture_text
from workflow.graph import compile_graph
from workflow.state import CandidateProfile, CopilotState, Job, ProfileBasic


def _session_id(prefix: str) -> str:
    """为每次真实调用生成独立 session_id，避免不同测试状态互相污染。"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _assert_has_substantive_resume_sections(state: CopilotState) -> None:
    """校验生成出的简历内容不是空壳。

    这里不要求某一个 section 必然出现，而是要求 skills / projects /
    internships / awards 中至少有一个非空，适配真实模型的轻微输出差异。
    """
    assert state.resume_content_json is not None
    section_counts = [
        len(state.resume_content_json.skills),
        len(state.resume_content_json.projects),
        len(state.resume_content_json.internships),
        len(state.resume_content_json.awards),
    ]
    assert any(count > 0 for count in section_counts)


def _build_job_from_fixture(jd_text: str) -> Job:
    """先通过真实 jd_node 生成 Job，供后续 content/workflow 测试复用。

    这样可以保证后续测试拿到的是和线上一致的结构化岗位对象，而不是手写假数据。
    """
    state = CopilotState(session_id=_session_id("int_jd_seed"), user_message=jd_text)
    updates = jd_node(state)
    return updates["job"]


def _build_candidate_profile_from_fixtures(material_text: str) -> CandidateProfile:
    """先通过真实 profile_node 生成 CandidateProfile，供后续测试复用。

    这里复用 profile fixture、project fixture、internship fixture 拼接后的材料，
    模拟用户一次性上传多份个人材料的场景。
    """
    state = CopilotState(session_id=_session_id("int_profile_seed"), user_message=material_text)
    updates = profile_node(state)
    return updates["candidate_profile"]


@pytest.fixture(scope="module", autouse=True)
def _real_llm_guard() -> None:
    """模块级守卫：只有显式开启配置时才运行真实 LLM 测试。"""
    if not should_run_real_llm_integration_tests():
        pytest.skip(
            "真实 LLM 集成测试默认关闭。运行前请在 config.yaml 中设置 "
            "testing.integration.run_real_llm_tests: true"
        )
    ensure_langsmith_enabled()


@pytest.fixture(scope="module")
def fixture_jd_text() -> str:
    return read_fixture_text("jds", "通用AIGC实习JD.md")


@pytest.fixture(scope="module")
def fixture_profile_text() -> str:
    return read_fixture_text("profiles", "虚拟候选人信息.md")


@pytest.fixture(scope="module")
def fixture_project_text() -> str:
    return read_fixture_text("projects", "求职Agent_README.md")


@pytest.fixture(scope="module")
def fixture_internship_text() -> str:
    return read_fixture_text("internships", "远望工业智能实习——RAG诊断平台.md")


@pytest.fixture(scope="module")
def combined_profile_material(fixture_profile_text: str, fixture_project_text: str, fixture_internship_text: str) -> str:
    """将多份个人材料拼成一次上传输入，模拟真实用户批量补充资料。"""
    return "\n\n".join([fixture_profile_text, fixture_project_text, fixture_internship_text])


def test_planner_node_recognizes_upload_jd_with_real_llm(fixture_jd_text: str) -> None:
    """测试 planner 单节点能把真实 JD 识别为 upload_jd。

    测试流程：
    1. 构造只包含 JD 文本和最小候选人信息的初始状态；
    2. 直接调用 planner_node，而不是整图；
    3. 校验意图识别结果和 execution_plan 是否以 jd_agent 开头。

    涉及的工作流阶段：
    只覆盖 workflow 入口的 Planner 阶段，不进入 jd_agent/content_agent/render_agent。
    """
    state = CopilotState(
        session_id=_session_id("int_planner_jd"),
        user_message=fixture_jd_text,
        candidate_profile=CandidateProfile(profile_basic=ProfileBasic(name="林知遥")),
    )

    # 真实 LLM 在这里负责意图分类与执行计划生成。
    updates = planner_node(state)

    assert updates["current_intent"] == "upload_jd"
    assert updates["execution_plan"]
    assert updates["execution_plan"][0] == "jd_agent"
    assert "jd_agent" in updates["triggered_agents"]


def test_jd_node_parses_real_fixture_with_real_llm(fixture_jd_text: str) -> None:
    """测试 jd_node 能把真实 JD fixture 解析成结构化 Job。

    测试流程：
    1. 构造仅包含 user_message=JD 文本的状态；
    2. 直接调用 jd_node；
    3. 校验输出 Job 至少包含 title 和若干结构化字段。

    涉及的工作流阶段：
    只覆盖 upload_jd 路径中的 JD Agent 阶段，不继续生成简历内容。
    """
    state = CopilotState(session_id=_session_id("int_jd"), user_message=fixture_jd_text)

    # jd_node 负责把原始岗位描述抽取为结构化岗位对象，并标记 content/render 需要更新。
    updates = jd_node(state)
    job = updates["job"]

    assert job.source == fixture_jd_text
    assert job.title
    assert any([
        bool(job.tech_stack),
        bool(job.keywords),
        bool(job.hard_skills),
        bool(job.responsibilities),
    ])
    assert updates["meta"].dirty_flags.content_dirty is True


def test_profile_node_extracts_candidate_profile_with_real_llm(combined_profile_material: str) -> None:
    """测试 profile_node 能从多份真实个人材料中构建候选人画像。

    测试流程：
    1. 将基本信息、项目经历、实习材料拼成一次 user_message；
    2. 直接调用 profile_node；
    3. 校验 profile_basic、materials、facts 等核心结构被填充。

    涉及的工作流阶段：
    只覆盖 upload_profile 路径中的 Profile Agent 阶段，不进入 content/render。
    """
    state = CopilotState(
        session_id=_session_id("int_profile"),
        user_message=combined_profile_material,
    )

    # profile_node 负责把用户原始材料沉淀为可复用的 CandidateProfile。
    updates = profile_node(state)
    profile = updates["candidate_profile"]

    assert profile.profile_basic.name == "林知遥"
    assert len(profile.materials) == 1
    assert profile.facts
    assert any(fact.type in {"skill", "project", "internship", "award"} for fact in profile.facts)


def test_content_node_generates_resume_content_with_real_llm(
    fixture_jd_text: str,
    combined_profile_material: str,
) -> None:
    """测试 content_node 能基于真实 Job 和 CandidateProfile 生成简历内容。

    测试流程：
    1. 先调用 jd_node 生成 Job；
    2. 再调用 profile_node 生成 CandidateProfile；
    3. 构造 current_intent=upload_profile 的状态并调用 content_node；
    4. 校验 resume_content_json 已生成，且目标岗位、姓名、核心 sections 合理。

    涉及的工作流阶段：
    覆盖 upload_profile 路径中的 Content Agent 阶段，但不包含 Render 阶段。
    """
    # 这里先用真实上游节点生成结构化输入，避免 content_node 吃到手工拼装的脏数据。
    job = _build_job_from_fixture(fixture_jd_text)
    candidate_profile = _build_candidate_profile_from_fixtures(combined_profile_material)
    state = CopilotState(
        session_id=_session_id("int_content"),
        current_intent="upload_profile",
        user_message=combined_profile_material,
        job=job,
        candidate_profile=candidate_profile,
    )

    # content_node 输出的是 ResumeContent 增量更新，需要合并回状态再做断言。
    updates = content_node(state)
    result_state = state.model_copy(update=updates)

    assert result_state.resume_content_json is not None
    assert result_state.resume_content_json.meta.target_role == job.title
    assert result_state.resume_content_json.profile.name == "林知遥"
    _assert_has_substantive_resume_sections(result_state)


def test_render_node_renders_html_with_real_llm(
    fixture_jd_text: str,
    combined_profile_material: str,
) -> None:
    """测试 render_node 能在真实内容基础上完成样式修改和 HTML 渲染。

    测试流程：
    1. 先通过 jd_node/profile_node/content_node 准备好可渲染的状态；
    2. 将 current_intent 改为 render_edit，并传入自然语言样式指令；
    3. 调用 render_node；
    4. 校验布局模式、HTML 产物和版本号更新。

    涉及的工作流阶段：
    覆盖 Render Agent 阶段。前置 content 生成只是为了让 render_node 有输入可消费。
    """
    job = _build_job_from_fixture(fixture_jd_text)
    candidate_profile = _build_candidate_profile_from_fixtures(combined_profile_material)
    content_state = CopilotState(
        session_id=_session_id("int_render_seed"),
        current_intent="upload_profile",
        user_message=combined_profile_material,
        job=job,
        candidate_profile=candidate_profile,
    )
    # 先生成 resume_content_json，再模拟用户发出“改成双栏布局”的渲染指令。
    content_updates = content_node(content_state)
    content_state = content_state.model_copy(update=content_updates)

    render_state = content_state.model_copy(update={
        "current_intent": "render_edit",
        "user_message": "请改成双栏布局，保持简洁、适合技术岗位投递。",
    })

    # render_node 会先解析渲染指令，再调用模板渲染器输出最终 HTML。
    updates = render_node(render_state)
    final_state = render_state.model_copy(update=updates)

    assert final_state.render_config.layout_mode == "double-column"
    assert "<html" in final_state.resume_html.html.lower()
    assert "林知遥" in final_state.resume_html.html
    assert final_state.meta.active_html_version >= 1


def test_workflow_upload_jd_runs_end_to_end_with_real_llm(
    fixture_jd_text: str,
    combined_profile_material: str,
) -> None:
    """测试 upload_jd 场景下整条 workflow 的真实端到端执行。

    测试流程：
    1. 先准备好候选人画像，避免 upload_jd 场景因没有 profile 而只停在 jd_agent；
    2. 编译 LangGraph 并调用 graph.invoke；
    3. 校验最终状态已经穿过 jd_agent、content_agent、render_agent。

    涉及的工作流路径：
    planner -> jd_agent -> content_agent -> render_agent -> respond
    """
    # upload_jd 只有在已有候选人画像时，才会继续生成简历内容并渲染 HTML。
    candidate_profile = _build_candidate_profile_from_fixtures(combined_profile_material)
    graph = compile_graph()
    state = CopilotState(
        session_id=_session_id("int_wf_jd"),
        user_message=fixture_jd_text,
        candidate_profile=candidate_profile,
    )

    # 这里测试的不再是单节点，而是 LangGraph 的真实条件路由与状态传播。
    result = graph.invoke(
        state.model_dump(),
        config={"run_name": "Integration-Workflow: Upload JD Real LLM"},
    )
    final_state = CopilotState.model_validate(result)

    assert final_state.current_intent == "upload_jd"
    assert final_state.job is not None
    _assert_has_substantive_resume_sections(final_state)
    assert final_state.resume_html.html
    assert final_state.meta.active_html_version >= 1


def test_workflow_upload_profile_runs_end_to_end_with_real_llm(
    fixture_jd_text: str,
    combined_profile_material: str,
) -> None:
    """测试 upload_profile 场景下整条 workflow 的真实端到端执行。

    测试流程：
    1. 先通过 jd_node 生成目标岗位，模拟“岗位已存在、用户继续补资料”的上下文；
    2. 编译 LangGraph 并调用 graph.invoke；
    3. 校验最终状态已经产出 candidate_profile、resume_content_json 和 HTML。

    涉及的工作流路径：
    planner -> profile_agent -> content_agent -> render_agent -> respond
    """
    # upload_profile 场景下如果 job 已存在，workflow 才会继续进入 content/render 阶段。
    job = _build_job_from_fixture(fixture_jd_text)
    graph = compile_graph()
    state = CopilotState(
        session_id=_session_id("int_wf_profile"),
        user_message=combined_profile_material,
        job=job,
    )

    result = graph.invoke(
        state.model_dump(),
        config={"run_name": "Integration-Workflow: Upload Profile Real LLM"},
    )
    final_state = CopilotState.model_validate(result)

    assert final_state.current_intent == "upload_profile"
    assert final_state.candidate_profile is not None
    _assert_has_substantive_resume_sections(final_state)
    assert final_state.resume_html.html
    assert "profile_agent" in final_state.triggered_agents