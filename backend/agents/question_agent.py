"""Question Agent — 基于当前 graph state 自由回答用户问题。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agents.json_contracts import QuestionAnswerOutput
from models.llm import get_llm, ainvoke_json_with_schema
from workflow.state import CopilotState
from workflow.rationales import append_section_rationales, summarize_user_message
from log import get_logger

logger = get_logger("agent")


_QUESTION_SYSTEM_PROMPT = """你是一个职业助手问答专家。你可以读取工作流 graph 的当前状态变量，并用自然语言回答用户问题。

回答要求：
- 优先依据状态变量中的事实回答，不要编造状态中没有的信息
- 如果信息不足，明确说明缺少哪些状态数据，并给出用户下一步可以补充什么
- 用户询问岗位、候选人、简历、缺口、追问问题、渲染配置、HTML 版本或面试问答时，都可以从状态变量中综合回答
- 回答要直接、自然，使用中文
- 返回且仅返回一个合法 JSON 对象
- 不要输出 Markdown、代码块、注释或额外说明
- section_rationales 用于给用户展示简要决策依据，不要输出内部逐步推理；每条 1 句话即可

返回格式如下：
{
  "answer": "给用户的直接回答",
  "section_rationales": [
    {
      "section": "问答",
      "decision": "说明本次回答主要依据了哪些状态信息",
      "reason": "解释为什么这些状态信息足以回答或为什么仍然信息不足",
      "evidence": ["当前状态中的简短依据"]
    }
  ]
}
"""


def _compact_state_context(state: CopilotState) -> dict[str, Any]:
    """构造给问答模型看的状态快照，避免把完整 HTML 塞进 prompt。"""
    state_context = state.model_dump(
        exclude={
            "user_attachments",
            "execution_plan",
            "triggered_agents",
            "reply_message",
            "agent_reply_message",
            "conversation_events",
            "section_rationales",
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
    try:
        parsed = await ainvoke_json_with_schema(llm, prompt, QuestionAnswerOutput, logger, "Question Agent")
    except RuntimeError as exc:
        logger.error("Question Agent failed: %s", exc)
        answer = "我暂时无法稳定解析当前问题的回答，请稍后重试或换一种问法。"
        return {
            "agent_reply_message": answer,
            "section_rationales": append_section_rationales(
                state,
                agent="question_agent",
                status="failed",
                fallback_section="问答",
                fallback_decision="暂时无法回答用户问题",
                fallback_reason="模型返回的问答结果不符合 JSON 约束，请重试。",
                fallback_evidence=[summarize_user_message(state.user_message)],
            )
        }

    answer = parsed.answer

    if not answer:
        answer = "我暂时没有从当前状态中找到可回答的信息。可以补充岗位、个人材料或先生成简历后再问我。"

    return {
        "agent_reply_message": answer,
        "section_rationales": append_section_rationales(
            state,
            agent="question_agent",
            rationales=parsed.section_rationales,
            fallback_section="问答",
            fallback_decision="基于当前会话状态回答用户问题",
            fallback_reason="回答优先引用已保存的岗位、候选人、简历、缺口和面试问答数据，避免编造状态外信息。",
            fallback_evidence=[summarize_user_message(state.user_message)],
        )
    }


def question_node(state: CopilotState) -> dict[str, Any]:
    """Question Agent 同步兼容入口。"""
    return asyncio.run(question_node_async(state))
