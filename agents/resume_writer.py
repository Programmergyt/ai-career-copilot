"""简历生成 Agent — 根据 JD 分析 + 个人材料生成结构化简历数据（JSON）"""

import json

from agents.llm import call_llm, parse_json_response
from prompts.resume_generation import (
    SECTION_GENERATION_SYSTEM, SECTION_GENERATION_USER,
    SECTION_FORMAT_INSTRUCTIONS,
    PROFILE_SECTION_SYSTEM, PROFILE_SECTION_USER,
)
from prompts.self_check import SELF_CHECK_SYSTEM, SELF_CHECK_USER


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


def generate_resume(
    jd_analysis: dict,
    section_contexts: dict[str, str],
    profile: dict | None = None,
) -> dict:
    """根据 JD 分析结果，按板块独立生成简历结构化数据。

    Args:
        jd_analysis: JD 分析结果字典
        section_contexts: 按类型分类的检索文本 {"项目经历": "...", "实习经历": "...", ...}
        profile: 提取的个人基本信息字典

    Returns:
        简历结构化数据字典（JSON 格式）
    """
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
    profile_raw = call_llm(PROFILE_SECTION_SYSTEM, profile_prompt)
    try:
        resume_data = parse_json_response(profile_raw)
    except (json.JSONDecodeError, Exception):
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
        section_content = call_llm(SECTION_GENERATION_SYSTEM, prompt)
        key = _DOC_TYPE_TO_KEY.get(doc_type, doc_type)
        resume_data[key] = section_content

    return resume_data


def self_check_resume(jd_analysis: dict, resume_content: str) -> dict:
    """对生成的简历做 JD 覆盖度自检。

    Returns:
        自检结果字典，包含 coverage_score / pass 等字段
    """
    prompt = SELF_CHECK_USER.format(
        jd_analysis=json.dumps(jd_analysis, ensure_ascii=False, indent=2),
        resume_content=resume_content,
    )
    raw = call_llm(SELF_CHECK_SYSTEM, prompt)

    try:
        return parse_json_response(raw)
    except json.JSONDecodeError:
        return {"raw_check": raw, "parse_error": True, "pass": False}
