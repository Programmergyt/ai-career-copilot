"""JD 分析 Agent — 深度解析岗位描述，输出结构化分析报告"""

import json
from openai import OpenAI

from prompts.jd_analysis import (
    JD_ANALYSIS_SYSTEM,
    JD_ANALYSIS_USER,
    JD_MATCH_SYSTEM,
    JD_MATCH_USER,
)
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
    """从 LLM 回复中解析 JSON，容忍 ```json 包裹。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # 去掉首尾 ``` 行
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


def analyze_jd(jd_text: str) -> dict:
    """分析 JD 文本，返回结构化的分析结果字典。"""
    client, model = _get_llm_client()

    prompt = JD_ANALYSIS_USER.format(jd_text=jd_text)
    raw = _call_llm(client, model, JD_ANALYSIS_SYSTEM, prompt)

    try:
        analysis = _parse_json_response(raw)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": raw, "parse_error": True}

    return analysis


def analyze_jd_with_match(
    jd_text: str,
    persist_directory: str | None = None,
) -> dict:
    """分析 JD 并进行个人匹配度评估。

    Returns:
        {"jd_analysis": {...}, "match_result": {...}}
    """
    # 第一步：分析 JD
    jd_analysis = analyze_jd(jd_text)

    # 第二步：RAG 检索个人知识库
    keywords = jd_analysis.get("keywords", [])
    tech_stack = jd_analysis.get("tech_stack", [])
    query = "，".join(keywords + tech_stack) if (keywords or tech_stack) else jd_text[:200]

    try:
        rag_results = retrieve(
            query=query,
            top_k=10,
            rerank_top_n=5,
            persist_directory=persist_directory,
        )
        personal_context = "\n\n".join(r["text"] for r in rag_results)
    except Exception:
        personal_context = "（个人知识库为空或检索失败）"
        rag_results = []

    # 第三步：LLM 匹配度分析
    client, model = _get_llm_client()
    match_prompt = JD_MATCH_USER.format(
        jd_analysis=json.dumps(jd_analysis, ensure_ascii=False, indent=2),
        personal_context=personal_context,
    )
    match_raw = _call_llm(client, model, JD_MATCH_SYSTEM, match_prompt)

    try:
        match_result = _parse_json_response(match_raw)
    except json.JSONDecodeError:
        match_result = {"raw_match": match_raw, "parse_error": True}

    return {
        "jd_analysis": jd_analysis,
        "match_result": match_result,
        "rag_results": rag_results,
    }
