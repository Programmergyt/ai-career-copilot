"""简历生成 Agent — 根据 JD 分析 + 个人材料生成定制化简历"""

import json
import os
from openai import OpenAI

from prompts.resume_generation import RESUME_GENERATION_SYSTEM, RESUME_GENERATION_USER
from prompts.self_check import SELF_CHECK_SYSTEM, SELF_CHECK_USER
from rag.retriever import retrieve


def _get_llm_client() -> tuple[OpenAI, str]:
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("LLM_API_BASE", "https://api.deepseek.com"),
    )
    return client, model


def _call_llm(client: OpenAI, model: str, system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=4096,
    )
    return resp.choices[0].message.content.strip()


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


def generate_resume(
    jd_analysis: dict,
    personal_context: str | None = None,
    persist_directory: str | None = None,
) -> str:
    """根据 JD 分析结果生成简历 Markdown 内容。

    Args:
        jd_analysis: JD 分析结果字典
        personal_context: 个人材料文本（如已有）；为 None 时自动 RAG 检索
        persist_directory: 向量库路径

    Returns:
        简历 Markdown 文本
    """
    # RAG 检索个人素材
    if personal_context is None:
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
            personal_context = "\n\n".join(r["text"] for r in rag_results)
        except Exception:
            personal_context = "（个人知识库为空或检索失败，请补充个人材料）"

    client, model = _get_llm_client()
    prompt = RESUME_GENERATION_USER.format(
        jd_analysis=json.dumps(jd_analysis, ensure_ascii=False, indent=2),
        personal_context=personal_context,
    )
    resume_md = _call_llm(client, model, RESUME_GENERATION_SYSTEM, prompt)
    return resume_md


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
