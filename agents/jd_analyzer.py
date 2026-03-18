"""JD 分析 Agent — 深度解析岗位描述，输出结构化分析报告"""

import json

from agents.llm import call_llm, parse_json_response
from prompts.jd_analysis import JD_ANALYSIS_SYSTEM, JD_ANALYSIS_USER


def analyze_jd(jd_text: str) -> dict:
    """分析 JD 文本，返回结构化的分析结果字典。"""
    prompt = JD_ANALYSIS_USER.format(jd_text=jd_text)
    raw = call_llm(JD_ANALYSIS_SYSTEM, prompt)

    try:
        analysis = parse_json_response(raw)
    except json.JSONDecodeError:
        analysis = {"raw_analysis": raw, "parse_error": True}

    return analysis
