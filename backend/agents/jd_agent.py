"""JD Agent — 解析岗位描述，输出结构化 Job。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from models.llm import get_llm, parse_json_response
from prompts.jd_analysis import JD_ANALYSIS_PROMPT
from workflow.state import CopilotState, Job
from log import get_logger

logger = get_logger("agent")


def jd_node(state: CopilotState) -> dict[str, Any]:
    """JD Agent 节点函数。"""
    logger.info("JD Agent started for session %s", state.session_id)

    jd_text = state.user_message

    prompt = JD_ANALYSIS_PROMPT.format(jd_text=jd_text)
    llm = get_llm()
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))
    parsed = parse_json_response(content)

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
        industry=parsed.get("industry", ""),
        title=parsed.get("title", ""),
        tech_stack=parsed.get("tech_stack", []),
        keywords=parsed.get("keywords", []),
        hard_skills=parsed.get("hard_skills", []),
        soft_skills=parsed.get("soft_skills", []),
        responsibilities=parsed.get("responsibilities", []),
        education_requirement=parsed.get("education_requirement", ""),
        experience_requirement=parsed.get("experience_requirement", ""),
        implicit_preferences=parsed.get("implicit_preferences", []),
        bonus_items=parsed.get("bonus_items", []),
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
        "reply_message": f"已解析岗位：{job.title}（{job.industry}）",
    }
