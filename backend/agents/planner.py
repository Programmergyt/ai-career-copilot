"""Planner Agent — intent resolution + serial plan building + validation."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agents.json_contracts import IntentClassificationOutput
from agents.registry import get_default_registry
from log import get_logger
from models.llm import ainvoke_json_with_schema, get_llm
from prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT
from workflow.plan_mode.plan_builder import build_plan_from_tasks
from workflow.plan_mode.task_extractor import extract_task_bundle
from workflow.plan_mode.plan_validator import PlanValidationError, validate_plan
from workflow.state import CopilotState

logger = get_logger("agent")


async def _classify_intent_async(state: CopilotState) -> IntentClassificationOutput:
    """Classify the user message into a supported workflow intent."""
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


async def _resolve_intent_async(state: CopilotState) -> IntentClassificationOutput:
    """Honor an explicit current_intent override when internal APIs provide one."""
    if state.intent_bundle:
        logger.info("Planner task bundle override detected: %s", state.intent_bundle)
        return IntentClassificationOutput(
            intent=state.intent_bundle[0],
            reason="task bundle override from existing state",
        )
    if state.current_intent:
        logger.info("Planner intent override detected: %s", state.current_intent)
        return IntentClassificationOutput(
            intent=state.current_intent,
            reason="intent override from existing state",
        )
    return await _classify_intent_async(state)


async def planner_node_async(state: CopilotState) -> dict[str, Any]:
    """Planner Agent async node."""
    logger.info("Planner Agent started for session %s", state.session_id)

    try:
        intent_result = await _resolve_intent_async(state)
    except RuntimeError as exc:
        logger.error("Planner Agent failed: %s", exc)
        return {
            "active_plan_id": "",
            "plan_status": "failed",
            "current_intent": "ask_question",
            "execution_plan": [],
            "execution_steps": [],
            "triggered_agents": [],
            "reply_message": "意图识别失败：模型输出格式异常，请稍后重试。",
        }

    intent = intent_result.intent or "ask_question"

    try:
        task_bundle = extract_task_bundle(intent, state)
        plan = build_plan_from_tasks(task_bundle, state, primary_intent=intent)
        execution_plan = [step.agent for step in plan.steps]
        validate_plan(plan, state, get_default_registry())
    except PlanValidationError as exc:
        logger.error("Planner generated invalid plan: %s", exc)
        return {
            "active_plan_id": "",
            "plan_status": "failed",
            "current_intent": intent,
            "execution_plan": [],
            "execution_steps": [],
            "triggered_agents": [],
            "reply_message": f"计划生成失败：{exc}",
        }

    logger.info("Execution plan: %s", execution_plan)
    logger.info("Execution steps: %s", [step.agent for step in plan.steps])

    message_id = state.meta.last_user_message_id or f"msg_{uuid.uuid4().hex[:12]}"
    updates: dict[str, Any] = {
        "active_plan_id": plan.plan_id,
        "plan_status": "planned",
        "current_intent": intent,
        "intent_bundle": plan.intent_bundle,
        "execution_plan": execution_plan,
        "execution_steps": plan.steps,
        "plan_policy": plan.policy,
        "triggered_agents": list(execution_plan),
        "last_plan_error": "",
        "replan_candidate": False,
    }

    if not execution_plan:
        if intent == "export":
            updates["reply_message"] = "导出功能将在后续版本中支持。"
        elif intent == "ask_question":
            updates["reply_message"] = intent_result.reason or "请提供更多信息。"

    updates["meta"] = state.meta.model_copy(update={
        "last_user_message_id": message_id,
    })

    return updates


def planner_node(state: CopilotState) -> dict[str, Any]:
    """Planner Agent sync entry."""
    return asyncio.run(planner_node_async(state))
