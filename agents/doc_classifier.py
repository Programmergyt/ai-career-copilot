"""文档分类与个人信息提取 Agent — 使用 LLM 对文档进行分类并提取个人基本信息"""

import json
from openai import OpenAI

from prompts.doc_classification import (
    DOC_CLASSIFICATION_SYSTEM,
    DOC_CLASSIFICATION_USER,
    PROFILE_EXTRACTION_SYSTEM,
    PROFILE_EXTRACTION_USER,
)
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


def _parse_json_response(text: str):
    """从 LLM 回复中解析 JSON，容忍 ```json 包裹。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


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

    # 构建文档摘要列表供 LLM 分类（截取前500字作为摘要）
    doc_summaries = []
    for i, doc in enumerate(parsed_docs):
        summary = doc["text"][:500] if len(doc["text"]) > 500 else doc["text"]
        doc_summaries.append(
            f"### 文档 {i + 1}\n- 文件路径: {doc['source_file']}\n- 内容摘要:\n{summary}\n"
        )

    doc_list_text = "\n".join(doc_summaries)

    client, model = _get_llm_client()
    prompt = DOC_CLASSIFICATION_USER.format(doc_list=doc_list_text)
    raw = _call_llm(client, model, DOC_CLASSIFICATION_SYSTEM, prompt)

    try:
        classifications = _parse_json_response(raw)
        # 构建 source_file -> doc_type 映射
        type_map = {}
        for item in classifications:
            src = item.get("source_file", "")
            dtype = item.get("doc_type", "project")
            if dtype not in VALID_DOC_TYPES:
                dtype = "项目经历"
            type_map[src] = dtype

        # 更新文档分类
        for doc in parsed_docs:
            if doc["source_file"] in type_map:
                doc["doc_type"] = type_map[doc["source_file"]]
    except (json.JSONDecodeError, KeyError):
        # 分类失败时保留原始 doc_type
        pass

    return parsed_docs


def extract_profile(parsed_docs: list[dict]) -> dict | None:
    """从 profile 类型文档中提取个人基本信息。

    Args:
        parsed_docs: 已分类的文档列表

    Returns:
        个人基本信息字典，或 None（无 profile 文档时）
    """
    profile_docs = [d for d in parsed_docs if d.get("doc_type") == "个人信息"]
    if not profile_docs:
        return None

    # 合并所有 profile 文档的文本
    profile_text = "\n\n---\n\n".join(d["text"] for d in profile_docs)

    client, model = _get_llm_client()
    prompt = PROFILE_EXTRACTION_USER.format(profile_text=profile_text)
    raw = _call_llm(client, model, PROFILE_EXTRACTION_SYSTEM, prompt)

    try:
        return _parse_json_response(raw)
    except json.JSONDecodeError:
        return {"raw_profile": raw, "parse_error": True}
