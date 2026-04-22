"""Question Answer Agent — 基于已有 state 回答用户问题。"""

from __future__ import annotations

import asyncio
from typing import Any

from agents.json_contracts import AskQuestionOutput
from log import get_logger
from models.llm import ainvoke_json_with_schema, get_llm
from prompts.question_answer import QUESTION_ANSWER_PROMPT
from workflow.state import CopilotState

logger = get_logger("agent")


def _dump_model_list(items: list[Any]) -> str:
    if not items:
        return "[]"
    return "[\n" + ",\n".join(item.model_dump_json() for item in items) + "\n]"


async def question_answer_node_async(state: CopilotState) -> dict[str, Any]:
    """Question Answer Agent 异步节点函数。"""
    logger.info("Question Answer Agent started for session %s", state.session_id)

    prompt = QUESTION_ANSWER_PROMPT.format(
        job_json=state.job.model_dump_json(indent=2) if state.job else "{}",
        profile_json=state.candidate_profile.model_dump_json(indent=2) if state.candidate_profile else "{}",
        resume_json=state.resume_content_json.model_dump_json(indent=2) if state.resume_content_json else "{}",
        gaps_json=_dump_model_list(state.gaps),
        questions_json=_dump_model_list(state.questions_to_ask),
        interview_json=_dump_model_list(state.interview_qa),
        user_question=state.user_message,
    )
    llm = get_llm()
    try:
        parsed = await ainvoke_json_with_schema(
            llm,
            prompt,
            AskQuestionOutput,
            logger,
            "Question Answer Agent",
        )
    except RuntimeError as exc:
        logger.error("Question Answer Agent failed: %s", exc)
        return {
            "reply_message": "问题回答失败：模型输出格式异常，请重试。",
        }

    answer = parsed.answer.strip()
    if not answer:
        answer = "当前信息不足，暂时无法给出可靠回答。你可以补充岗位、个人材料或简历内容后再试。"

    return {
        "reply_message": answer,
    }


def question_answer_node(state: CopilotState) -> dict[str, Any]:
    """Question Answer Agent 同步兼容入口。"""
    return asyncio.run(question_answer_node_async(state))
