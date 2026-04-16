"""测试辅助工具：fixture 读取、Fake LLM、LangSmith 初始化。"""

from __future__ import annotations

import json
import os
from pathlib import Path

from models.llm import setup_langsmith
from tools.file_parser import parse_file


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def read_fixture_text(category: str, filename: str) -> str:
    """读取测试夹具中的真实文件内容。"""
    return parse_file(FIXTURES_DIR / category / filename)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class PromptRouterLLM:
    """基于 prompt 关键字返回可预测 JSON 的 LLM 假实现。"""

    def __init__(self, intent: str = "upload_jd") -> None:
        self.intent = intent

    def invoke(self, prompt):
        text = prompt if isinstance(prompt, str) else str(prompt)

        if "意图分类器" in text:
            return _FakeResponse(json.dumps({
                "intent": self.intent,
                "reason": f"mocked intent={self.intent}",
            }, ensure_ascii=False))

        if "岗位需求分析专家" in text:
            return _FakeResponse(json.dumps({
                "industry": "互联网",
                "title": "AIGC工程师",
                "tech_stack": ["Python", "LangChain", "RAG"],
                "keywords": ["Generative AI", "LLM"],
                "hard_skills": ["Python", "RAG"],
                "soft_skills": ["沟通协作"],
                "responsibilities": ["构建企业级 GenAI 应用"],
                "education_requirement": "硕士及以上",
                "experience_requirement": "有 AI 项目经历",
                "implicit_preferences": ["快速原型能力"],
                "bonus_items": ["Agentic Workflow"],
            }, ensure_ascii=False))

        if "候选人画像构建专家" in text:
            return _FakeResponse(json.dumps({
                "profile_basic": {
                    "name": "郭奕廷",
                    "email": "2403508140@qq.com",
                    "phone": "+86-13585926126",
                    "city": "上海",
                    "school": "华东理工大学",
                },
                "facts": [
                    {
                        "id": "fact_skill_1",
                        "type": "skill",
                        "content": "Python + LangChain + RAG",
                        "source_refs": ["material_mock"],
                        "updated_at": "",
                    },
                    {
                        "id": "fact_project_1",
                        "type": "project",
                        "content": "AI Career Copilot 多 Agent 项目",
                        "source_refs": ["material_mock"],
                        "updated_at": "",
                    },
                ],
            }, ensure_ascii=False))

        if "简历内容生成专家" in text or "简历内容编辑专家" in text:
            return _FakeResponse(json.dumps({
                "profile": {
                    "name": "郭奕廷",
                    "email": "2403508140@qq.com",
                    "phone": "+86-13585926126",
                    "city": "上海",
                    "github": "https://github.com/guoyiting",
                    "education": [
                        {
                            "id": "edu_1",
                            "school": "华东理工大学",
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
                        "title": "上海新华控制 — RAG 故障诊断",
                        "content": "负责 RAG 检索与重排链路，提升诊断准确率。",
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "projects": [
                    {
                        "id": "proj_1",
                        "title": "AI Career Copilot",
                        "content": "基于 LangGraph 的多 Agent 简历系统。",
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "awards": [
                    {
                        "id": "award_1",
                        "title": "华为杯二等奖",
                        "content": "2025年研究生数学建模竞赛二等奖。",
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "papers": [],
            }, ensure_ascii=False))

        if "渲染配置专家" in text:
            return _FakeResponse(json.dumps({
                "template_id": "default",
                "theme": "light",
                "font_family": "Source Han Sans",
                "font_size": 15,
                "line_height": 1.6,
                "page_margin": {"top": 24, "right": 24, "bottom": 24, "left": 24},
                "section_order": ["profile", "skills", "projects", "internships", "awards"],
                "dense_mode": False,
                "accent_style": "minimal",
                "visibility_map": {},
                "layout_mode": "double-column",
                "spacing_scale": "standard",
                "last_render_reason": "按用户要求调整为双栏布局",
            }, ensure_ascii=False))

        if "能力缺口分析专家" in text:
            return _FakeResponse(json.dumps({
                "gaps": [
                    {
                        "id": "gap_1",
                        "type": "missing_skill",
                        "severity": "high",
                        "description": "缺少 RAG 实战经验",
                        "related_section_ids": ["projects"],
                        "resolved": False,
                        "resolution_source": "gap_analysis",
                    }
                ],
                "questions_to_ask": [
                    {
                        "id": "q_1",
                        "question": "你是否参与过 RAG 项目的开发？",
                        "reason": "补充项目经验细节",
                        "target_field": "projects",
                        "priority": "high",
                        "status": "pending",
                        "answer_ref": "",
                    }
                ]
            }, ensure_ascii=False))

        if "面试准备专家" in text:
            return _FakeResponse(json.dumps([
                {
                    "id": "qa_1",
                    "category": "technical",
                    "question": "请介绍你在 RAG 项目中的角色和技术架构。",
                    "answer": "我负责构建检索-生成闭环，并使用 LangChain 与 Chroma 实现高效向量检索。",
                    "source_refs": ["projects"],
                    "version": 1,
                },
                {
                    "id": "qa_2",
                    "category": "project_deep_dive",
                    "question": "这个项目如何保证模型输出的准确性？",
                    "answer": "通过检索结果预过滤、Prompt 设计与后处理规则，显著降低了 hallucination 风险。",
                    "source_refs": ["projects"],
                    "version": 1,
                },
                {
                    "id": "qa_3",
                    "category": "behavioral",
                    "question": "你在团队协作中如何处理需求变更？",
                    "answer": "我会及时与产品和研发对齐，拆解风险并调整迭代优先级。",
                    "source_refs": [],
                    "version": 1,
                }
            ], ensure_ascii=False))

        return _FakeResponse(json.dumps({"intent": "ask_question", "reason": "fallback"}, ensure_ascii=False))


def patch_all_agent_llm(monkeypatch, llm: PromptRouterLLM) -> None:
    """将所有 Agent 模块中的 get_llm 打桩为同一假实例。"""
    import agents.planner as planner
    import agents.jd_agent as jd_agent
    import agents.profile_agent as profile_agent
    import agents.gap_agent as gap_agent
    import agents.content_agent as content_agent
    import agents.render_agent as render_agent
    import agents.interview_agent as interview_agent

    monkeypatch.setattr(planner, "get_llm", lambda: llm)
    monkeypatch.setattr(jd_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(profile_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(gap_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(content_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(render_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(interview_agent, "get_llm", lambda: llm)


def ensure_langsmith_enabled() -> str | None:
    """启用 LangSmith 并返回项目 URL。"""
    url = setup_langsmith()
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_PROJECT")
    return url
