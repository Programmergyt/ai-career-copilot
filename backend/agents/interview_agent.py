"""Interview Agent — 生成面试问答集。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agents.json_contracts import InterviewGenerationOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.interview_generation import INTERVIEW_GENERATION_PROMPT
from workflow.state import CopilotState, InterviewQA
from workflow.rationales import append_section_rationales
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
            "section_rationales": append_section_rationales(
                state,
                agent="interview_agent",
                status="skipped",
                fallback_section="面试准备",
                fallback_decision="暂不生成面试问答",
                fallback_reason="面试问答需要同时参考岗位、候选人画像和简历内容，目前数据还不完整。",
                fallback_evidence=[
                    f"岗位信息：{'已提供' if state.job is not None else '缺失'}",
                    f"候选人画像：{'已提供' if state.candidate_profile is not None else '缺失'}",
                    f"简历内容：{'已提供' if state.resume_content_json is not None else '缺失'}",
                ],
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
            "section_rationales": append_section_rationales(
                state,
                agent="interview_agent",
                status="failed",
                fallback_section="面试准备",
                fallback_decision="暂时无法生成面试问答",
                fallback_reason="模型返回的面试问答不符合 JSON 约束，请重试。",
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
        "section_rationales": append_section_rationales(
            state,
            agent="interview_agent",
            rationales=parsed.section_rationales,
            fallback_section="面试准备",
            fallback_decision=f"生成 {len(interview_qa)} 条面试问答",
            fallback_reason="这些问题覆盖岗位要求和简历经历中最可能被面试官深挖的交叉点。",
            fallback_evidence=sorted({item.category for item in interview_qa}),
        ),
    }


def interview_node(state: CopilotState) -> dict[str, Any]:
    """Interview Agent 同步兼容入口。"""
    return asyncio.run(interview_node_async(state))
