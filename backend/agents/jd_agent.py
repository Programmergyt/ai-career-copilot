"""JD Agent — 解析岗位描述，输出结构化 Job。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.json_contracts import JDAnalysisOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.jd_analysis import JD_ANALYSIS_PROMPT
from workflow.state import CopilotState, Job
from workflow.trace import append_trace, summarize_user_message
from log import get_logger

logger = get_logger("agent")


async def jd_node_async(state: CopilotState) -> dict[str, Any]:
    """JD Agent 异步节点函数。"""
    logger.info("JD Agent started for session %s", state.session_id)

    jd_text = state.user_message

    prompt = JD_ANALYSIS_PROMPT.format(jd_text=jd_text)
    llm = get_llm()
    try:
        parsed = await ainvoke_json_with_schema(llm, prompt, JDAnalysisOutput, logger, "JD Agent")
    except RuntimeError as exc:
        logger.error("JD Agent failed: %s", exc)
        return {
            "workflow_trace": append_trace(
                state,
                node="jd_agent",
                status="failed",
                input_summary=f"解析岗位文本：{summarize_user_message(jd_text)}",
                output_summary="岗位解析失败：模型输出格式异常，请重试。",
                error=str(exc),
            ),
        }

    now = datetime.now(timezone.utc).isoformat()
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    version = 1
    if state.job is not None:
        version = state.job.version + 1

    job = Job(
        id=job_id,
        source=jd_text,
        parsed_at=now,
        version=version,
        industry=parsed.industry,
        title=parsed.title,
        tech_stack=parsed.tech_stack,
        keywords=parsed.keywords,
        hard_skills=parsed.hard_skills,
        soft_skills=parsed.soft_skills,
        responsibilities=parsed.responsibilities,
        education_requirement=parsed.education_requirement,
        experience_requirement=parsed.experience_requirement,
        implicit_preferences=parsed.implicit_preferences,
        bonus_items=parsed.bonus_items,
    )

    logger.info("JD parsed: %s (v%d)", job.title, job.version)

    # 设置 dirty flags
    meta = state.meta.model_copy(update={
        "dirty_flags": state.meta.dirty_flags.model_copy(update={
            "content_dirty": True,
            "render_dirty": True,
            "interview_dirty": True,
        })
    })

    return {
        "job": job,
        "meta": meta,
        "workflow_trace": append_trace(
            state,
            node="jd_agent",
            input_summary=f"解析岗位文本：{summarize_user_message(jd_text)}",
            output_summary=f"已解析岗位：{job.title}（{job.industry}）。",
            artifacts={
                "job_title": job.title,
                "industry": job.industry,
                "tech_stack_count": len(job.tech_stack),
                "hard_skill_count": len(job.hard_skills),
                "responsibility_count": len(job.responsibilities),
                "version": job.version,
            },
        ),
    }


def jd_node(state: CopilotState) -> dict[str, Any]:
    """JD Agent 同步兼容入口。"""
    return asyncio.run(jd_node_async(state))
