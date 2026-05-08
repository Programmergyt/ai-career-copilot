"""Resume Content Agent ↔ Gap Analysis Agent 闭环测试。

验证：
- gap_agent 产出的 ``state.gaps`` 会被 content_agent 序列化为 JSON 注入 prompt；
- content_agent 在生成简历时按 gap 的 related_section_ids 给出针对性改写
  （关键词出现在对应 section 的 content 中）；
- 已 resolved 的 gap 不会进入 prompt；
- content_agent 仍只写入 resume_content_json / meta / workflow_trace，
  不会回写 gaps / job / candidate_profile / render_config / resume_html / interview_qa。

运行：python -m pytest backend/test/agent/test_content_agent_gap_alignment.py -sv
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from agents.gap_agent import gap_node
from agents.content_agent import content_node, _serialize_gaps_for_prompt
from workflow.state import (
    CopilotState, Job, CandidateProfile, ProfileBasic, Fact, Gap,
)
from test.test_support import (
    PromptRouterLLM,
    patch_all_agent_llm,
    ensure_langsmith_enabled,
)


# ---- Fakes ---------------------------------------------------------------


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class GapAwareContentLLM(PromptRouterLLM):
    """对 Gap Analysis 与 Resume Content 两条 prompt 路径做精细化打桩。

    - 对 Gap Analysis prompt：返回固定的 ``missing_skill`` / ``no_quantification`` /
      已 resolved 三条 gap，便于断言 prompt 注入与过滤；
    - 对 Resume Content prompt：在执行前对 prompt 做断言（确认 gaps_json
      被注入且已过滤掉 resolved），随后产出会反映对应 gap 的简历内容。
    """

    GAP_LANGGRAPH_DESC = "缺少 LangGraph 多 Agent 编排实战经验"
    GAP_QUANT_DESC = "实习经历缺少量化效果（请用百分比或数量描述成果）"
    GAP_RESOLVED_DESC = "此 gap 已在前一轮解决，不应再注入 prompt"

    def __init__(self) -> None:
        super().__init__(intent="upload_jd")
        self.last_resume_prompt: str | None = None

    def invoke(self, prompt):
        text = prompt if isinstance(prompt, str) else str(prompt)

        if "能力缺口分析专家" in text:
            return _FakeResponse(json.dumps({
                "gaps": [
                    {
                        "id": "gap_skill_langgraph",
                        "type": "missing_skill",
                        "severity": "high",
                        "description": self.GAP_LANGGRAPH_DESC,
                        "related_section_ids": ["projects"],
                        "resolved": False,
                        "resolution_source": "gap_analysis",
                    },
                    {
                        "id": "gap_no_quant_intern",
                        "type": "no_quantification",
                        "severity": "high",
                        "description": self.GAP_QUANT_DESC,
                        "related_section_ids": ["internships"],
                        "resolved": False,
                        "resolution_source": "gap_analysis",
                    },
                    {
                        "id": "gap_already_resolved",
                        "type": "missing_skill",
                        "severity": "low",
                        "description": self.GAP_RESOLVED_DESC,
                        "related_section_ids": ["skills"],
                        "resolved": True,
                        "resolution_source": "user_answer",
                    },
                ],
                "questions_to_ask": [
                    {
                        "id": "q_1",
                        "question": "你是否在项目中实际编排过多 Agent 工作流？",
                        "reason": "补充 LangGraph 经验",
                        "target_field": "projects",
                        "priority": "high",
                        "status": "pending",
                        "answer_ref": "",
                    }
                ],
            }, ensure_ascii=False))

        if "简历内容生成专家" in text or "简历内容编辑专家" in text:
            self.last_resume_prompt = text
            # 断言 gaps_json 真的进了 prompt，且已过滤掉 resolved 项
            assert self.GAP_LANGGRAPH_DESC in text, (
                "Resume prompt 必须包含未 resolved 的 missing_skill gap 描述"
            )
            assert self.GAP_QUANT_DESC in text, (
                "Resume prompt 必须包含未 resolved 的 no_quantification gap 描述"
            )
            assert self.GAP_RESOLVED_DESC not in text, (
                "已 resolved 的 gap 不应被注入 Resume prompt"
            )

            return _FakeResponse(json.dumps({
                "profile": {
                    "name": "林知遥",
                    "email": "lin.zhiyou@example.test",
                    "phone": "+86-13900001234",
                    "city": "杭州",
                    "github": "https://github.com/linzhiyou-demo",
                    "education": [
                        {
                            "id": "edu_1",
                            "school": "星海理工大学",
                            "major": "控制工程",
                            "degree": "硕士",
                            "start_date": "2025-09",
                            "end_date": "2028-06",
                        }
                    ],
                },
                "summary": "聚焦 AIGC 与 RAG 的候选人，具备多 Agent 应用开发经验。",
                "skills": [
                    {
                        "id": "skill_1",
                        "title": "Python / LangChain",
                        "content": "熟练构建 RAG 工作流与工具链。",
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "internships": [
                    {
                        "id": "intern_1",
                        "title": "远望工业智能 — RAG 诊断平台（实习）",
                        "content": (
                            "负责 RAG 检索-重排链路重构，把诊断准确率提升 35%，"
                            "线上召回延迟下降 40%（量化对齐 no_quantification gap）。"
                        ),
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "projects": [
                    {
                        "id": "proj_1",
                        "title": "AI Career Copilot",
                        "content": (
                            "基于 LangGraph 的多 Agent 简历系统，编排 planner / jd / profile / "
                            "gap / content / render / interview 多节点工作流，4 周完成 MVP。"
                        ),
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "awards": [],
                "papers": [],
            }, ensure_ascii=False))

        return super().invoke(prompt)


# ---- Fixtures ------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _langsmith_monitoring():
    ensure_langsmith_enabled()


@pytest.fixture
def gap_aware_state() -> CopilotState:
    return CopilotState(
        session_id="sess_gap_to_content",
        current_intent="upload_jd",
        user_message="LangGraph 多 Agent 编排岗位 JD",
        job=Job(
            id="job_1",
            title="AIGC工程师",
            tech_stack=["Python", "LangGraph", "RAG"],
            keywords=["Multi-Agent", "Workflow"],
            hard_skills=["Python", "RAG", "LangGraph"],
        ),
        candidate_profile=CandidateProfile(
            profile_basic=ProfileBasic(name="林知遥"),
            facts=[
                Fact(id="fact_1", type="skill", content="Python + LangChain", source_refs=[]),
                Fact(id="fact_2", type="project", content="多 Agent 简历系统", source_refs=[]),
                Fact(id="fact_3", type="internship", content="RAG 诊断平台后端实习", source_refs=[]),
            ],
        ),
    )


# ---- Tests ---------------------------------------------------------------


def test_serialize_gaps_for_prompt_filters_resolved_and_orders_by_severity():
    state = CopilotState(
        session_id="sess_unit",
        gaps=[
            Gap(id="g_low", type="missing_skill", severity="low", description="低优先级"),
            Gap(id="g_high", type="missing_skill", severity="high", description="高优先级"),
            Gap(id="g_resolved", type="missing_skill", severity="high",
                description="已解决的不应出现", resolved=True),
            Gap(id="g_med", type="no_quantification", severity="medium", description="中优先级"),
        ],
    )

    payload = json.loads(_serialize_gaps_for_prompt(state))
    ids = [item["id"] for item in payload]

    assert ids == ["g_high", "g_med", "g_low"], "应过滤 resolved 并按 severity 高→低排序"
    assert all("resolution_source" not in item for item in payload), (
        "序列化结果不应外泄 resolution_source 等内部字段"
    )


def test_serialize_gaps_for_prompt_returns_empty_array_when_no_gaps():
    state = CopilotState(session_id="sess_empty")
    assert _serialize_gaps_for_prompt(state) == "[]"

    state_all_resolved = CopilotState(
        session_id="sess_all_resolved",
        gaps=[
            Gap(id="g1", type="missing_skill", severity="high", description="x", resolved=True),
        ],
    )
    assert _serialize_gaps_for_prompt(state_all_resolved) == "[]"


def test_gap_to_content_pipeline_addresses_gaps_in_related_sections(
    monkeypatch, gap_aware_state: CopilotState
):
    """gap_agent → content_agent 闭环：content 必须把 gaps 反映到 related sections。"""
    llm = GapAwareContentLLM()
    patch_all_agent_llm(monkeypatch, llm)

    # 1. gap_agent 产出 gaps（含 resolved 项）
    gap_updates = gap_node(gap_aware_state)
    assert gap_updates["gaps"], "gap_agent 应产出 gaps"
    assert any(g.severity == "high" and not g.resolved for g in gap_updates["gaps"])
    assert any(g.resolved for g in gap_updates["gaps"]), "夹具中至少应有一条已 resolved gap"

    state_after_gap = gap_aware_state.model_copy(update={
        "gaps": gap_updates["gaps"],
        "questions_to_ask": gap_updates["questions_to_ask"],
    })

    # 2. content_agent 读取 state.gaps 并生成简历
    content_updates = content_node(state_after_gap)

    # 2a. 契约边界：content_agent 仅可写 resume_content_json / meta / workflow_trace
    forbidden_keys = {
        "gaps", "questions_to_ask", "job", "candidate_profile",
        "render_config", "resume_html", "interview_qa",
    }
    leaked = forbidden_keys & set(content_updates.keys())
    assert not leaked, f"content_agent 越界写入禁写字段：{leaked}"
    assert set(content_updates.keys()) <= {"resume_content_json", "meta", "workflow_trace"}

    # 2b. 针对性改写：至少一个 gap 的关键词出现在其 related section
    resume = content_updates["resume_content_json"]
    projects_text = " ".join(item.content for item in resume.projects)
    internships_text = " ".join(item.content for item in resume.internships)

    addressed: list[str] = []
    if "LangGraph" in projects_text:
        addressed.append("missing_skill→projects")
    if "%" in internships_text:
        addressed.append("no_quantification→internships")

    assert addressed, (
        "至少要有一个 gap 在对应 section 得到针对性改写，"
        f"projects={projects_text!r}, internships={internships_text!r}"
    )

    # 2c. trace 工件应反映已注入的未 resolved gap 数（夹具里是 2 条）
    last_trace = content_updates["workflow_trace"][-1]
    assert last_trace.node == "content_agent"
    assert last_trace.artifacts.get("gap_count_injected") == 2

    # 2d. last_resume_prompt 已被赋值（说明 fake 的断言路径被走过了）
    assert llm.last_resume_prompt is not None
    assert "对齐缺口" in llm.last_resume_prompt


def test_content_node_works_when_gaps_empty(monkeypatch, gap_aware_state: CopilotState):
    """state.gaps 为空时 content_agent 仍应正常生成（向后兼容旧流程）。"""
    llm = PromptRouterLLM(intent="upload_jd")
    patch_all_agent_llm(monkeypatch, llm)

    state_no_gaps = gap_aware_state.model_copy(update={"gaps": []})
    updates = content_node(state_no_gaps)

    assert "resume_content_json" in updates
    assert updates["workflow_trace"][-1].artifacts.get("gap_count_injected") == 0


def test_content_edit_path_also_injects_gaps(monkeypatch, gap_aware_state: CopilotState):
    """content_edit 走 RESUME_SECTION_UPDATE_PROMPT 分支时也必须注入 gaps_json。"""
    captured: dict[str, Any] = {}

    class _CaptureLLM(GapAwareContentLLM):
        def invoke(self, prompt):
            text = prompt if isinstance(prompt, str) else str(prompt)
            if "简历内容编辑专家" in text:
                captured["edit_prompt"] = text
            return super().invoke(prompt)

    llm = _CaptureLLM()
    patch_all_agent_llm(monkeypatch, llm)

    # 先按 upload_jd 路径生成一份基线 resume_content_json，state 必须带 gaps
    # 才能让 GapAwareContentLLM 的内嵌断言通过（这正是验收的一部分）。
    seeded_gaps = [
        Gap(
            id="gap_skill_langgraph",
            type="missing_skill",
            severity="high",
            description=GapAwareContentLLM.GAP_LANGGRAPH_DESC,
            related_section_ids=["projects"],
            resolved=False,
        ),
        Gap(
            id="gap_no_quant_intern",
            type="no_quantification",
            severity="high",
            description=GapAwareContentLLM.GAP_QUANT_DESC,
            related_section_ids=["internships"],
            resolved=False,
        ),
    ]
    seeded_state = gap_aware_state.model_copy(update={"gaps": seeded_gaps})
    initial = content_node(seeded_state)

    state_with_resume = seeded_state.model_copy(update={
        "resume_content_json": initial["resume_content_json"],
        "current_intent": "content_edit",
        "user_message": "请把项目部分按 LangGraph 关键词补充",
    })

    content_node(state_with_resume)

    assert "edit_prompt" in captured, "content_edit 路径应触发 RESUME_SECTION_UPDATE_PROMPT"
    assert GapAwareContentLLM.GAP_LANGGRAPH_DESC in captured["edit_prompt"], (
        "局部更新路径也必须注入 gaps_json"
    )
