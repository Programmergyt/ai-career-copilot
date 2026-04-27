"""Interview Agent — 生成面试问答集。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agents.json_contracts import InterviewGenerationOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.interview_generation import INTERVIEW_GENERATION_PROMPT
from workflow.state import CopilotState, InterviewQA
from workflow.trace import append_trace
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
            "interview_qa": [],
            "workflow_trace": append_trace(
                state,
                node="interview_agent",
                status="skipped",
                input_summary="读取岗位、候选人画像和简历内容生成面试问答。",
                output_summary="数据不完整，无法生成面试问答。",
                artifacts={
                    "has_job": state.job is not None,
                    "has_candidate_profile": state.candidate_profile is not None,
                    "has_resume_content": state.resume_content_json is not None,
                },
            ),
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
            "interview_qa": [],
            "workflow_trace": append_trace(
                state,
                node="interview_agent",
                status="failed",
                input_summary="读取岗位、候选人画像和简历内容生成面试问答。",
                output_summary="面试问答生成失败：模型输出格式异常，请重试。",
                error=str(exc),
            ),
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
        "workflow_trace": append_trace(
            state,
            node="interview_agent",
            input_summary="读取岗位、候选人画像和简历内容生成面试问答。",
            output_summary=f"面试问答已生成，共 {len(interview_qa)} 条。",
            artifacts={
                "interview_qa_count": len(interview_qa),
                "categories": sorted({item.category for item in interview_qa}),
            },
        ),
    }


def interview_node(state: CopilotState) -> dict[str, Any]:
    """Interview Agent 同步兼容入口。"""
    return asyncio.run(interview_node_async(state))
