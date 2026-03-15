"""简历生成 Agent — 根据 JD 分析 + 个人材料生成结构化简历数据（JSON）"""

import json
from openai import OpenAI

from prompts.resume_generation import (
    RESUME_GENERATION_SYSTEM, RESUME_GENERATION_USER,
    SECTION_GENERATION_SYSTEM, SECTION_GENERATION_USER,
    SECTION_FORMAT_INSTRUCTIONS,
    PROFILE_SECTION_SYSTEM, PROFILE_SECTION_USER,
)
from prompts.self_check import SELF_CHECK_SYSTEM, SELF_CHECK_USER
from rag.retriever import retrieve
from config_loader import get_llm_config


def _get_llm_client() -> tuple[OpenAI, str]:
    cfg = get_llm_config()
    client = OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["api_base"],
    )
    return client, cfg["model"]


def _call_llm(client: OpenAI, model: str, system: str, user: str) -> str:
    cfg = get_llm_config()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
    )
    return resp.choices[0].message.content.strip()


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


DOC_TYPE_LABELS = {
    "项目经历": "项目经历",
    "实习经历": "实习/工作经历",
    "专业技能": "专业技能",
    "论文成果": "论文与学术成果",
}

# JSON 字段名与文档类型的映射
_DOC_TYPE_TO_KEY = {
    "专业技能": "skills",
    "项目经历": "projects",
    "实习经历": "internship",
    "论文成果": "papers",
}

# 分板块生成时的板块顺序
_SECTION_ORDER = ["专业技能", "项目经历", "实习经历", "论文成果"]


def _generate_resume_data(
    jd_analysis: dict,
    section_contexts: dict[str, str],
    profile: dict | None = None,
) -> dict:
    """按板块独立生成简历结构化数据（JSON dict），每个板块只接收自己类型的材料。

    Returns:
        简历结构化数据字典，包含 name/email/phone/github/education/awards/skills/projects/internship/papers 等字段。
    """
    client, model = _get_llm_client()
    jd_text = json.dumps(jd_analysis, ensure_ascii=False, indent=2)

    # ---- 1. 个人信息 / 教育背景 / 获奖 → LLM 输出 JSON ----
    profile_text = (
        json.dumps(profile, ensure_ascii=False, indent=2)
        if profile
        else "（未提取到个人基本信息，请标注 TODO）"
    )
    profile_prompt = PROFILE_SECTION_USER.format(
        profile=profile_text, jd_analysis=jd_text,
    )
    profile_raw = _call_llm(client, model, PROFILE_SECTION_SYSTEM, profile_prompt)
    try:
        resume_data = _parse_json_response(profile_raw)
    except (json.JSONDecodeError, Exception):
        # 解析失败时使用 profile 中的原始字段
        resume_data = {
            "name": (profile or {}).get("name", ""),
            "email": (profile or {}).get("email", ""),
            "phone": (profile or {}).get("phone", ""),
            "github": (profile or {}).get("github", ""),
            "education": (profile or {}).get("education", ""),
            "awards": (profile or {}).get("awards", ""),
        }

    # ---- 2. 各内容板块独立生成（每次 LLM 调用只看到该类型的材料） ----
    for doc_type in _SECTION_ORDER:
        materials = section_contexts.get(doc_type)
        if not materials or not materials.strip():
            continue

        label = DOC_TYPE_LABELS.get(doc_type, doc_type)
        format_inst = SECTION_FORMAT_INSTRUCTIONS.get(
            doc_type,
            f"输出「{label}」相关内容。",
        )
        prompt = SECTION_GENERATION_USER.format(
            section_name=label,
            jd_analysis=jd_text,
            section_materials=materials,
            format_instructions=format_inst,
        )
        section_content = _call_llm(client, model, SECTION_GENERATION_SYSTEM, prompt)
        key = _DOC_TYPE_TO_KEY.get(doc_type, doc_type)
        resume_data[key] = section_content

    return resume_data


def generate_resume(
    jd_analysis: dict,
    section_contexts: dict[str, str] | None = None,
    personal_context: str | None = None,
    persist_directory: str | None = None,
    profile: dict | None = None,
) -> dict:
    """根据 JD 分析结果生成简历结构化数据。

    Args:
        jd_analysis: JD 分析结果字典
        section_contexts: 按类型分类的检索文本 {"项目经历": "...", "实习经历": "...", ...}
        personal_context: 兼容旧接口，合并的个人材料文本
        persist_directory: 向量库路径
        profile: 提取的个人基本信息字典

    Returns:
        简历结构化数据字典（JSON 格式）
    """
    # 分板块独立生成
    if section_contexts:
        return _generate_resume_data(jd_analysis, section_contexts, profile)

    # === 以下为旧的单 Prompt 兼容路径 ===
    if personal_context is not None:
        categorized_context = personal_context
    else:
        keywords = jd_analysis.get("keywords", [])
        tech_stack = jd_analysis.get("tech_stack", [])
        responsibilities = jd_analysis.get("core_responsibilities", [])
        query_parts = keywords + tech_stack + responsibilities
        query = "，".join(query_parts) if query_parts else "个人项目经历技能"

        try:
            rag_results = retrieve(
                query=query,
                top_k=10,
                rerank_top_n=5,
                persist_directory=persist_directory,
            )
            categorized_context = "\n\n".join(r["text"] for r in rag_results)
        except Exception:
            categorized_context = "（个人知识库为空或检索失败，请补充个人材料）"

    available_sections = list(section_contexts.keys()) if section_contexts else []

    client, model = _get_llm_client()
    profile_text = json.dumps(profile, ensure_ascii=False, indent=2) if profile else "（未提取到个人基本信息，请从材料中推断或标注 TODO）"
    section_instructions = _build_section_instructions(available_sections)

    prompt = RESUME_GENERATION_USER.format(
        jd_analysis=json.dumps(jd_analysis, ensure_ascii=False, indent=2),
        personal_context=categorized_context,
        profile=profile_text,
        section_instructions=section_instructions,
    )
    resume_md = _call_llm(client, model, RESUME_GENERATION_SYSTEM, prompt)
    # 旧路径返回纯 Markdown 文本，包装为 dict 以保持接口一致
    return {"_raw_markdown": resume_md}


def _build_section_instructions(available_sections: list[str]) -> str:
    """根据实际可用的文档类型，生成简历板块指令。"""
    all_types = ["项目经历", "实习经历", "专业技能", "论文成果"]
    lines = []
    for t in all_types:
        label = DOC_TYPE_LABELS[t]
        if t in available_sections:
            lines.append(f"- {label}：有材料，请根据材料撰写此板块")
        else:
            lines.append(f"- {label}：无材料，请跳过此板块（不要输出该标题）")
    return "\n".join(lines)


def self_check_resume(jd_analysis: dict, resume_content: str) -> dict:
    """对生成的简历做 JD 覆盖度自检。

    Returns:
        自检结果字典，包含 coverage_score / pass 等字段
    """
    client, model = _get_llm_client()
    prompt = SELF_CHECK_USER.format(
        jd_analysis=json.dumps(jd_analysis, ensure_ascii=False, indent=2),
        resume_content=resume_content,
    )
    raw = _call_llm(client, model, SELF_CHECK_SYSTEM, prompt)

    try:
        return _parse_json_response(raw)
    except json.JSONDecodeError:
        return {"raw_check": raw, "parse_error": True, "pass": False}


def generate_resume_with_reflection(
    jd_analysis: dict,
    personal_context: str | None = None,
    persist_directory: str | None = None,
    max_rounds: int = 2,
) -> tuple[str, list[dict]]:
    """带 Reflection 自检的简历生成。

    Returns:
        (最终简历 Markdown, 自检历史列表)
    """
    resume = generate_resume(jd_analysis, personal_context, persist_directory)
    check_history = []

    for _ in range(max_rounds):
        check = self_check_resume(jd_analysis, resume)
        check_history.append(check)

        if check.get("pass", False):
            break

        # 未通过，重新生成（把自检建议加入 context）
        suggestions = check.get("improvement_suggestions", [])
        if suggestions:
            extra_context = "\n\n## 改进建议（来自上一轮自检）\n" + "\n".join(
                f"- {s}" for s in suggestions
            )
            resume = generate_resume(
                jd_analysis,
                (personal_context or "") + extra_context,
                persist_directory,
            )

    return resume, check_history
