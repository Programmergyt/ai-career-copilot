"""Gap Analysis Agent — 比对 JD 与候选人画像，输出能力缺口和待追问问题。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from models.llm import get_llm, parse_json_response
from prompts.gap_analysis import GAP_ANALYSIS_PROMPT
from workflow.state import CopilotState, Gap, Question
from log import get_logger

logger = get_logger("agent")


def _build_gap_list(parsed: dict) -> list[Gap]:
    gaps: list[Gap] = []
    for item in parsed.get("gaps", []):
        gaps.append(Gap(
            id=item.get("id", f"gap_{uuid.uuid4().hex[:12]}"),
            type=item.get("type", "missing_skill"),
            severity=item.get("severity", "medium"),
            description=item.get("description", ""),
            related_section_ids=item.get("related_section_ids", []),
            resolved=item.get("resolved", False),
            resolution_source=item.get("resolution_source", "gap_analysis"),
        ))
    return gaps


def _build_question_list(parsed: dict) -> list[Question]:
    questions: list[Question] = []
    for item in parsed.get("questions_to_ask", []):
        questions.append(Question(
            id=item.get("id", f"q_{uuid.uuid4().hex[:12]}"),
            question=item.get("question", ""),
            reason=item.get("reason", ""),
            target_field=item.get("target_field", ""),
            priority=item.get("priority", "medium"),
            status=item.get("status", "pending"),
            answer_ref=item.get("answer_ref", ""),
        ))
    return questions


def gap_node(state: CopilotState) -> dict[str, Any]:
    """Gap Analysis Agent 节点函数。"""
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
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))

    parsed = {}
    try:
        parsed = parse_json_response(content)
    except Exception as exc:  # noqa: BLE001
        logger.error("Gap Analysis parse failed: %s", exc)
        parsed = {"gaps": [], "questions_to_ask": []}

    gaps = _build_gap_list(parsed)
    questions = _build_question_list(parsed)

    logger.info("Gap Analysis generated %d gaps and %d questions", len(gaps), len(questions))

    return {
        "gaps": gaps,
        "questions_to_ask": questions,
        "reply_message": "缺失信息分析已完成。",
    }
