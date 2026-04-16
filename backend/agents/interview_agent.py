"""Interview Agent — 生成面试问答集。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from models.llm import get_llm, parse_json_response
from prompts.interview_generation import INTERVIEW_GENERATION_PROMPT
from workflow.state import CopilotState, InterviewQA
from log import get_logger

logger = get_logger("agent")


def _build_interview_qa(parsed: Any) -> list[InterviewQA]:
    interview_qa: list[InterviewQA] = []
    items = parsed if isinstance(parsed, list) else parsed.get("interview_qa", [])
    for item in items:
        interview_qa.append(InterviewQA(
            id=item.get("id", f"qa_{uuid.uuid4().hex[:12]}"),
            category=item.get("category", "technical"),
            question=item.get("question", ""),
            answer=item.get("answer", ""),
            source_refs=item.get("source_refs", []),
            version=item.get("version", 1),
        ))
    return interview_qa


def interview_node(state: CopilotState) -> dict[str, Any]:
    """Interview Agent 节点函数。"""
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
    response = llm.invoke(prompt)
    content = getattr(response, "content", str(response))

    parsed = []
    try:
        parsed = parse_json_response(content)
    except Exception as exc:  # noqa: BLE001
        logger.error("Interview QA parse failed: %s", exc)
        parsed = []

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
        "reply_message": "面试问答已生成。",
    }
