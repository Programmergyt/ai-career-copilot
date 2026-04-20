"""Gap Analysis Agent — 比对 JD 与候选人画像，输出能力缺口和待追问问题。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agents.json_contracts import GapAnalysisOutput
from models.llm import get_llm, ainvoke_json_with_schema, invoke_json_with_schema
from prompts.gap_analysis import GAP_ANALYSIS_PROMPT
from workflow.state import CopilotState, Gap, Question
from log import get_logger

logger = get_logger("agent")


def _build_gap_list(parsed: GapAnalysisOutput) -> list[Gap]:
    gaps: list[Gap] = []
    for item in parsed.gaps:
        gaps.append(Gap(
            id=item.id or f"gap_{uuid.uuid4().hex[:12]}",
            type=item.type,
            severity=item.severity,
            description=item.description,
            related_section_ids=item.related_section_ids,
            resolved=item.resolved,
            resolution_source=item.resolution_source,
        ))
    return gaps


def _build_question_list(parsed: GapAnalysisOutput) -> list[Question]:
    questions: list[Question] = []
    for item in parsed.questions_to_ask:
        questions.append(Question(
            id=item.id or f"q_{uuid.uuid4().hex[:12]}",
            question=item.question,
            reason=item.reason,
            target_field=item.target_field,
            priority=item.priority,
            status=item.status,
            answer_ref=item.answer_ref,
        ))
    return questions


async def gap_node_async(state: CopilotState) -> dict[str, Any]:
    """Gap Analysis Agent 异步节点函数。"""
    logger.info("Gap Analysis Agent started for session %s", state.session_id)

    if state.job is None or state.candidate_profile is None:
        logger.warning("Gap Analysis skipped due to missing job or profile")
        return {
            "reply_message": "缺少岗位或候选人画像，暂时无法完成缺失信息分析。",
            "gaps": [],
            "questions_to_ask": [],
        }

    prompt = GAP_ANALYSIS_PROMPT.format(
        job_json=state.job.model_dump_json(indent=2),
        profile_json=state.candidate_profile.model_dump_json(indent=2),
    )
    llm = get_llm()
    try:
        parsed = await ainvoke_json_with_schema(llm, prompt, GapAnalysisOutput, logger, "Gap Analysis Agent")
    except RuntimeError as exc:
        logger.error("Gap Analysis Agent failed: %s", exc)
        return {
            "reply_message": "缺失信息分析失败：模型输出格式异常，请重试。",
            "gaps": [],
            "questions_to_ask": [],
        }

    gaps = _build_gap_list(parsed)
    questions = _build_question_list(parsed)

    logger.info("Gap Analysis generated %d gaps and %d questions", len(gaps), len(questions))

    return {
        "gaps": gaps,
        "questions_to_ask": questions,
        "reply_message": "缺失信息分析已完成。请在右侧缺失信息栏目查看最新内容。",
    }


def gap_node(state: CopilotState) -> dict[str, Any]:
    """Gap Analysis Agent 同步兼容入口。"""
    return asyncio.run(gap_node_async(state))
