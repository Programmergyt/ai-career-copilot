"""Planner Agent — 意图分类 + 执行计划生成 + 执行元数据镜像。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agents.json_contracts import IntentClassificationOutput
from agents.planner_metadata import build_plan_metadata
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT
from workflow.state import CopilotState
from log import get_logger

logger = get_logger("agent")

async def _classify_intent_async(state: CopilotState) -> IntentClassificationOutput:
    """异步调用 LLM 进行意图分类。"""
    prompt = INTENT_CLASSIFICATION_PROMPT.format(
        has_job=state.job is not None,
        has_profile=state.candidate_profile is not None,
        has_resume=state.resume_content_json is not None,
        user_message=state.user_message,
    )
    llm = get_llm()
    result = await ainvoke_json_with_schema(llm, prompt, IntentClassificationOutput, logger, "Planner Agent")
    logger.info("Intent classified: %s (reason: %s)", result.intent, result.reason)
    return result
async def planner_node_async(state: CopilotState) -> dict[str, Any]:
    """Planner Agent 异步节点函数。"""
    logger.info("Planner Agent started for session %s", state.session_id)

    # 1. 意图分类
    try:
        intent_result = await _classify_intent_async(state)
    except RuntimeError as exc:
        logger.error("Planner Agent failed: %s", exc)
        return {
            "active_plan_id": "",
            "current_intent": "ask_question",
            "execution_plan": [],
            "execution_steps": [],
            "triggered_agents": [],
            "reply_message": "意图识别失败：模型输出格式异常，请稍后重试。",
        }

    intent = intent_result.intent or "ask_question"

    # 2. 构建执行计划与结构化 step 元数据
    plan_id, plan, execution_steps = build_plan_metadata(intent, state)
    logger.info("Execution plan: %s", plan)
    logger.info("Execution steps: %s", [step.agent for step in execution_steps])

    # 3. 生成消息 ID 和事件
    message_id = f"msg_{uuid.uuid4().hex[:12]}"

    updates: dict[str, Any] = {
        "active_plan_id": plan_id,
        "current_intent": intent,
        "execution_plan": plan,
        "execution_steps": execution_steps,
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


def planner_node(state: CopilotState) -> dict[str, Any]:
    """Planner Agent 同步兼容入口。"""
    return asyncio.run(planner_node_async(state))
