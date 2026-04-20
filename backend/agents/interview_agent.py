"""Interview Agent — 生成面试问答集。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agents.json_contracts import InterviewGenerationOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.interview_generation import INTERVIEW_GENERATION_PROMPT
from workflow.state import CopilotState, InterviewQA
from log import get_logger

logger = get_logger("agent")


def _build_interview_qa(parsed: InterviewGenerationOutput) -> list[InterviewQA]:
    interview_qa: list[InterviewQA] = []
    for item in parsed.interview_qa:
        interview_qa.append(InterviewQA(
            id=item.id or f"qa_{uuid.uuid4().hex[:12]}",
            category=item.category,
            question=item.question,
            answer=item.answer,
            source_refs=item.source_refs,
            version=item.version,
        ))
    return interview_qa


async def interview_node_async(state: CopilotState) -> dict[str, Any]:
    """Interview Agent 异步节点函数。"""
    logger.info("Interview Agent started for session %s", state.session_id)

    if state.job is None or state.candidate_profile is None or state.resume_content_json is None:
        logger.warning("Interview Agent skipped due to incomplete state")
        return {
            "reply_message": "数据不完整，无法生成面试问答。",
            "interview_qa": [],
        }

    prompt = INTERVIEW_GENERATION_PROMPT.format(
        job_json=state.job.model_dump_json(indent=2),
        profile_json=state.candidate_profile.model_dump_json(indent=2),
        resume_json=state.resume_content_json.model_dump_json(indent=2),
    )
    llm = get_llm()
    try:
        parsed = await ainvoke_json_with_schema(llm, prompt, InterviewGenerationOutput, logger, "Interview Agent")
    except RuntimeError as exc:
        logger.error("Interview Agent failed: %s", exc)
        return {
            "reply_message": "面试问答生成失败：模型输出格式异常，请重试。",
            "interview_qa": [],
        }

    interview_qa = _build_interview_qa(parsed)

    logger.info("Interview Agent generated %d QAs", len(interview_qa))

    meta = state.meta.model_copy(update={
        "dirty_flags": state.meta.dirty_flags.model_copy(update={
            "interview_dirty": False,
        })
    })

    return {
        "interview_qa": interview_qa,
        "meta": meta,
        "reply_message": "面试问答已生成。请在右侧面试问答栏目查看最新内容。",
    }


def interview_node(state: CopilotState) -> dict[str, Any]:
    """Interview Agent 同步兼容入口。"""
    return asyncio.run(interview_node_async(state))
