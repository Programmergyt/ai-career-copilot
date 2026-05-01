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

    def bind(self, **kwargs):
        return self

    async def ainvoke(self, prompt):
        return self.invoke(prompt)

    def invoke(self, prompt):
        text = prompt if isinstance(prompt, str) else str(prompt)

        if "意图分类器" in text:
            return _FakeResponse(json.dumps({
                "intent": self.intent,
                "reason": f"mocked intent={self.intent}",
                "section_rationales": [
                    {
                        "section": "需求理解",
                        "decision": f"识别为 {self.intent}",
                        "reason": "测试桩根据预设 intent 返回处理路径。",
                        "evidence": ["mocked intent"],
                    }
                ],
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
                "section_rationales": [
                    {
                        "section": "岗位分析",
                        "decision": "提取 AIGC 工程师的核心要求",
                        "reason": "RAG、LangChain 和企业级 GenAI 应用会影响后续简历匹配。",
                        "evidence": ["RAG", "LangChain", "GenAI"],
                    }
                ],
            }, ensure_ascii=False))

        if "候选人画像构建专家" in text:
            return _FakeResponse(json.dumps({
                "profile_basic": {
                    "name": "林知遥",
                    "email": "lin.zhiyou@example.test",
                    "phone": "+86-13900001234",
                    "city": "杭州",
                    "school": "星海理工大学",
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
                "section_rationales": [
                    {
                        "section": "候选人画像",
                        "decision": "沉淀候选人的技能和项目事实",
                        "reason": "这些事实会支撑后续简历生成和缺口分析。",
                        "evidence": ["Python + LangChain + RAG", "AI Career Copilot"],
                    }
                ],
            }, ensure_ascii=False))

        if "简历内容生成专家" in text or "简历内容编辑专家" in text:
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
                        "title": "远望工业智能 — RAG 诊断平台",
                        "content": "基于工业故障知识库负责 RAG 检索与重排链路，融合关键词检索、向量召回和 Cross-Encoder 重排。\n优化诊断问答的检索覆盖率与答案相关性，支撑工业故障知识检索落地。\n沉淀可复用的检索评估流程，为后续召回和重排策略迭代提供依据。",
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "projects": [
                    {
                        "id": "proj_1",
                        "title": "AI Career Copilot",
                        "content": "基于 LangGraph 设计多 Agent 求职辅助系统，串联 JD 解析、简历生成、渲染与面试问答流程。\n实现内容生成与渲染配置分离，使简历修改后可自动触发 HTML 预览更新。\n交付可端到端运行的职业助手原型，提升简历内容生成与岗位匹配分析效率。",
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "awards": [
                    {
                        "id": "award_1",
                        "title": "启明星创新奖学金",
                        "content": "获得校级创新奖学金与项目实践奖励。",
                        "source_refs": [],
                        "updated_at": "",
                    }
                ],
                "papers": [],
                "section_rationales": [
                    {
                        "section": "简历内容",
                        "decision": "突出 AIGC 与 RAG 相关经历",
                        "reason": "这些经历最贴近目标岗位的技术栈和职责要求。",
                        "evidence": ["RAG", "多 Agent 简历系统"],
                    }
                ],
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
                "section_rationales": [
                    {
                        "section": "视觉呈现",
                        "decision": "调整为双栏布局",
                        "reason": "用户明确要求改成双栏布局。",
                        "evidence": ["改成双栏布局"],
                    }
                ],
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
                ],
                "section_rationales": [
                    {
                        "section": "匹配差距",
                        "decision": "将 RAG 实战经验列为高优先级缺口",
                        "reason": "目标岗位强调 RAG，而候选人画像还需要更具体的项目细节。",
                        "evidence": ["RAG", "项目经验"],
                    }
                ],
            }, ensure_ascii=False))

        if "面试准备专家" in text:
            return _FakeResponse(json.dumps({
                "interview_qa": [
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
                ],
                "section_rationales": [
                    {
                        "section": "面试准备",
                        "decision": "围绕 RAG 技术和项目深挖生成问题",
                        "reason": "这些问题覆盖岗位技术要求和简历中最可能被追问的项目经历。",
                        "evidence": ["RAG 项目", "技术架构"],
                    }
                ],
            }, ensure_ascii=False))

        if "职业助手问答专家" in text or "当前 graph state JSON" in text:
            return _FakeResponse(json.dumps({
                "answer": "当前状态显示目标岗位是 AIGC工程师，候选人是林知遥。",
                "section_rationales": [
                    {
                        "section": "问答",
                        "decision": "依据当前状态回答目标岗位和候选人",
                        "reason": "状态中已经保存了 job.title 和 candidate_profile.profile_basic.name。",
                        "evidence": ["AIGC工程师", "林知遥"],
                    }
                ],
            }, ensure_ascii=False))

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
    import agents.question_agent as question_agent

    monkeypatch.setattr(planner, "get_llm", lambda: llm)
    monkeypatch.setattr(jd_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(profile_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(gap_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(content_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(render_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(interview_agent, "get_llm", lambda: llm)
    monkeypatch.setattr(question_agent, "get_llm", lambda: llm)


def ensure_langsmith_enabled() -> str | None:
    """启用 LangSmith 并返回项目 URL。"""
    url = setup_langsmith()
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_PROJECT")
    return url
