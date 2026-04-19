"""Planner Agent — 意图分类 + 执行计划生成 + 事件记录。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.json_contracts import IntentClassificationOutput
from models.llm import get_llm, invoke_json_with_schema
from prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT
from workflow.state import CopilotState
from log import get_logger

logger = get_logger("agent")

# Intent → 执行链路
_INTENT_PLAN: dict[str, list[str]] = {
    "upload_jd": ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"],
    "upload_profile": ["profile_agent", "content_agent", "render_agent", "interview_agent"],
    "content_edit": ["content_agent", "render_agent"],
    "render_edit": ["render_agent"],
    "export": [],
    "ask_question": ["gap_agent"],
}


def _classify_intent(state: CopilotState) -> IntentClassificationOutput:
    """调用 LLM 进行意图分类。"""
    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        has_job=state.job is not None,
        has_profile=state.candidate_profile is not None,
        has_resume=state.resume_content_json is not None,
        user_message=state.user_message,
    )
    llm = get_llm()
    result = invoke_json_with_schema(llm, prompt, IntentClassificationOutput, logger, "Planner Agent")
    logger.info("Intent classified: %s (reason: %s)", result.intent, result.reason)
    return result


def _build_execution_plan(intent: str, state: CopilotState) -> list[str]:
    """根据 intent 和当前状态构建执行计划。"""
    base_plan = _INTENT_PLAN.get(intent, [])

    # 跳过逻辑
    if intent == "upload_jd" and state.candidate_profile is None:
        # 没有候选人数据，不能生成简历
        return ["jd_agent"]

    return list(base_plan)


def planner_node(state: CopilotState) -> dict[str, Any]:
    """Planner Agent 节点函数。"""
    logger.info("Planner Agent started for session %s", state.session_id)

    # 1. 意图分类
    try:
        intent_result = _classify_intent(state)
    except RuntimeError as exc:
        logger.error("Planner Agent failed: %s", exc)
        return {
            "current_intent": "ask_question",
            "execution_plan": [],
            "triggered_agents": [],
            "reply_message": "意图识别失败：模型输出格式异常，请稍后重试。",
        }

    intent = intent_result.intent or "ask_question"

    # 2. 构建执行计划
    plan = _build_execution_plan(intent, state)
    logger.info("Execution plan: %s", plan)

    # 3. 生成消息 ID 和事件
    message_id = f"msg_{uuid.uuid4().hex[:12]}"

    updates: dict[str, Any] = {
        "current_intent": intent,
        "execution_plan": plan,
        "triggered_agents": list(plan),
    }

    # 无需执行 Agent 的意图直接回复
    if not plan:
        if intent == "export":
            updates["reply_message"] = "导出功能将在后续版本中支持。"
        elif intent == "ask_question":
            updates["reply_message"] = intent_result.reason or "请提供更多信息。"

    updates["meta"] = state.meta.model_copy(update={
        "last_user_message_id": message_id,
    })

    return updates
