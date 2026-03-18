"""文档分类、个人信息提取与技能提炼 Agent"""

import json

from agents.llm import call_llm, parse_json_response
from prompts.doc_classification import (
    DOC_CLASSIFICATION_SYSTEM,
    DOC_CLASSIFICATION_USER,
    PROFILE_EXTRACTION_SYSTEM,
    PROFILE_EXTRACTION_USER,
)
from prompts.skill_refinement import SKILL_REFINEMENT_SYSTEM, SKILL_REFINEMENT_USER


VALID_DOC_TYPES = {"个人信息", "项目经历", "实习经历", "专业技能", "论文成果"}


def classify_documents(parsed_docs: list[dict]) -> list[dict]:
    """使用 LLM 对解析后的文档进行分类。

    Args:
        parsed_docs: [{"text": str, "source_file": str, "doc_type": str}, ...]

    Returns:
        更新了 doc_type 的文档列表
    """
    if not parsed_docs:
        return parsed_docs

    doc_summaries = []
    for i, doc in enumerate(parsed_docs):
        summary = doc["text"][:500] if len(doc["text"]) > 500 else doc["text"]
        doc_summaries.append(
            f"### 文档 {i + 1}\n- 文件路径: {doc['source_file']}\n- 内容摘要:\n{summary}\n"
        )

    doc_list_text = "\n".join(doc_summaries)
    prompt = DOC_CLASSIFICATION_USER.format(doc_list=doc_list_text)
    raw = call_llm(DOC_CLASSIFICATION_SYSTEM, prompt)

    try:
        classifications = parse_json_response(raw)
        type_map = {}
        for item in classifications:
            src = item.get("source_file", "")
            dtype = item.get("doc_type", "project")
            if dtype not in VALID_DOC_TYPES:
                dtype = "项目经历"
            type_map[src] = dtype

        for doc in parsed_docs:
            if doc["source_file"] in type_map:
                doc["doc_type"] = type_map[doc["source_file"]]
    except (json.JSONDecodeError, KeyError):
        pass

    return parsed_docs


def extract_profile(parsed_docs: list[dict]) -> dict | None:
    """从 profile 类型文档中提取个人基本信息。"""
    profile_docs = [d for d in parsed_docs if d.get("doc_type") == "个人信息"]
    if not profile_docs:
        return None

    profile_text = "\n\n---\n\n".join(d["text"] for d in profile_docs)
    prompt = PROFILE_EXTRACTION_USER.format(profile_text=profile_text)
    raw = call_llm(PROFILE_EXTRACTION_SYSTEM, prompt)

    try:
        return parse_json_response(raw)
    except json.JSONDecodeError:
        return {"raw_profile": raw, "parse_error": True}


def refine_skill_documents(parsed_docs: list[dict], jd_analysis: dict) -> list[dict]:
    """使用 LLM 对「专业技能」类文档进行提炼，只保留与 JD 相关的技能。

    提示词包含岗位描述，要求 LLM 针对 JD 进行选择和优化。

    Args:
        parsed_docs: 已分类的文档列表
        jd_analysis: JD 分析结果

    Returns:
        更新了 text 字段的文档列表（技能类文档被提炼）
    """
    jd_text = json.dumps(jd_analysis, ensure_ascii=False, indent=2)

    for doc in parsed_docs:
        if doc.get("doc_type") != "专业技能":
            continue

        prompt = SKILL_REFINEMENT_USER.format(
            jd_analysis=jd_text,
            skill_text=doc["text"],
        )
        refined = call_llm(SKILL_REFINEMENT_SYSTEM, prompt)
        doc["text_original"] = doc["text"]  # 保留原始文本
        doc["text"] = refined

    return parsed_docs
