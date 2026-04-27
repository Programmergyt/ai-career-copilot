"""Question Agent — 基于当前 graph state 自由回答用户问题。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from models.llm import get_llm, _ainvoke_model, _extract_text_content
from workflow.state import CopilotState
from workflow.trace import append_trace, summarize_user_message
from log import get_logger

logger = get_logger("agent")


_QUESTION_SYSTEM_PROMPT = """你是一个职业助手问答专家。你可以读取工作流 graph 的当前状态变量，并用自然语言回答用户问题。

回答要求：
- 优先依据状态变量中的事实回答，不要编造状态中没有的信息
- 如果信息不足，明确说明缺少哪些状态数据，并给出用户下一步可以补充什么
- 用户询问岗位、候选人、简历、缺口、追问问题、渲染配置、HTML 版本或面试问答时，都可以从状态变量中综合回答
- 回答要直接、自然，使用中文
"""


def _compact_state_context(state: CopilotState) -> dict[str, Any]:
    """构造给问答模型看的状态快照，避免把完整 HTML 塞进 prompt。"""
    state_context = state.model_dump(
        exclude={
            "user_attachments",
            "execution_plan",
            "triggered_agents",
            "reply_message",
            "conversation_events",
            "workflow_trace",
        }
    )
    resume_html = state_context.get("resume_html") or {}
    html = resume_html.get("html") or ""
    if html:
        resume_html["html"] = html[:3000]
        resume_html["html_truncated"] = len(html) > 3000
        state_context["resume_html"] = resume_html
    return state_context


async def question_node_async(state: CopilotState) -> dict[str, Any]:
    """Question Agent 异步节点函数。"""
    logger.info("Question Agent started for session %s", state.session_id)

    state_json = json.dumps(_compact_state_context(state), ensure_ascii=False, indent=2)
    prompt = (
        f"{_QUESTION_SYSTEM_PROMPT}\n\n"
        "用户问题：\n"
        f"{state.user_message}\n\n"
        "当前 graph state JSON：\n"
        f"{state_json}"
    )
    llm = get_llm()
    response = await _ainvoke_model(llm, prompt)
    answer = _extract_text_content(response)

    if not answer:
        answer = "我暂时没有从当前状态中找到可回答的信息。可以补充岗位、个人材料或先生成简历后再问我。"

    return {
        "workflow_trace": append_trace(
            state,
            node="question_agent",
            input_summary=f"根据当前 graph state 回答问题：{summarize_user_message(state.user_message)}",
            output_summary=answer,
            artifacts={"answer_length": len(answer)},
        )
    }


def question_node(state: CopilotState) -> dict[str, Any]:
    """Question Agent 同步兼容入口。"""
    return asyncio.run(question_node_async(state))
