"""Planner Agent — 意图分类 + 执行计划生成 + 事件记录。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from agents.json_contracts import IntentClassificationOutput
from models.llm import get_llm, ainvoke_json_with_schema
from prompts.intent_classification import INTENT_CLASSIFICATION_PROMPT
from workflow.state import CopilotState
from workflow.rationales import append_section_rationales, summarize_user_message
from log import get_logger

logger = get_logger("agent")

# Intent → 执行链路
_INTENT_PLAN: dict[str, list[str]] = {
    "upload_jd": ["jd_agent", "gap_agent", "content_agent", "render_agent", "interview_agent"],
    "upload_profile": ["profile_agent", "content_agent", "render_agent", "interview_agent"],
    "gap_analysis": ["gap_agent"],
    "content_edit": ["content_agent", "render_agent"],
    "render_edit": ["render_agent"],
    "export": [],
    "ask_question": ["question_agent"],
}


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


def _build_execution_plan(intent: str, state: CopilotState) -> list[str]:
    """根据 intent 和当前状态构建执行计划。"""
    base_plan = _INTENT_PLAN.get(intent, [])

    # 跳过逻辑
    if intent == "upload_jd" and state.candidate_profile is None:
        # 没有候选人数据，不能生成简历
        return ["jd_agent"]

    return list(base_plan)


async def planner_node_async(state: CopilotState) -> dict[str, Any]:
    """Planner Agent 异步节点函数。"""
    logger.info("Planner Agent started for session %s", state.session_id)

    # 1. 意图分类
    try:
        intent_result = await _classify_intent_async(state)
    except RuntimeError as exc:
        logger.error("Planner Agent failed: %s", exc)
        return {
            "current_intent": "ask_question",
            "execution_plan": [],
            "triggered_agents": [],
            "section_rationales": append_section_rationales(
                state,
                agent="planner",
                status="failed",
                fallback_section="需求理解",
                fallback_decision="暂时无法稳定识别用户意图",
                fallback_reason="模型返回的意图分类结果不符合 JSON 约束，请稍后重试或换一种表达。",
                fallback_evidence=[summarize_user_message(state.user_message)],
            ),
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
        "section_rationales": append_section_rationales(
            state,
            agent="planner",
            rationales=intent_result.section_rationales,
            fallback_section="需求理解",
            fallback_decision=f"识别为 {intent} 并安排 {' -> '.join(plan) if plan else '直接回复'}",
            fallback_reason=intent_result.reason or "根据用户消息和当前会话状态选择最合适的处理路径。",
            fallback_evidence=[summarize_user_message(state.user_message)],
        ),
    }

    # 无需执行 Agent 的意图直接回复
    if not plan:
        if intent == "export":
            updates["section_rationales"] = append_section_rationales(
                state.model_copy(update={"section_rationales": updates["section_rationales"]}),
                agent="export",
                status="skipped",
                fallback_section="导出",
                fallback_decision="暂不执行导出",
                fallback_reason="当前导出能力还未接入主对话流程，因此只保留用户请求并给出说明。",
            )

    updates["meta"] = state.meta.model_copy(update={
        "last_user_message_id": message_id,
    })

    return updates


def planner_node(state: CopilotState) -> dict[str, Any]:
    """Planner Agent 同步兼容入口。"""
    return asyncio.run(planner_node_async(state))
